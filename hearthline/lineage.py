"""工件归属、拆合交接和同秒冲突的领域规则。

输入层接受少量常见别名字段；规范化后统一使用 ``workpieces`` 与
``transfers``。分析层只把 ``state == "effective"`` 的交接用于归属变化。
"""

from collections import defaultdict

from .errors import Problem
from .fields import ident, number, rows


PIECE_ID_KEYS = ('id', 'workpiece', 'piece', 'workpiece_id', 'piece_id',
                 'workpiece_no', 'piece_no', 'serial', 'serial_no')
PIECE_TRAY_KEYS = ('initial_tray', 'initial_tray_id', 'tray', 'tray_id', 'start_tray',
                   'start_tray_id', 'from_tray', 'from_tray_id', 'base_tray',
                   'initial_plate', 'plate')
PIECE_SINCE_KEYS = ('since', 'from_s', 'start_s', 'at')

MOVE_PIECE_KEYS = ('workpiece', 'piece', 'id', 'workpiece_id', 'piece_id')
MOVE_FROM_KEYS = ('from_tray', 'from_tray_id', 'source_tray', 'source_tray_id',
                  'from', 'source', 'origin_tray', 'origin_tray_id', 'origin')
MOVE_TO_KEYS = ('to_tray', 'to_tray_id', 'destination_tray', 'destination_tray_id',
                'target_tray', 'target_tray_id', 'to', 'destination', 'dest', 'target')

TRANSFER_ID_KEYS = ('id', 'transfer_id', 'handoff_id', 'handover_id', 'movement_id')
TRANSFER_AT_KEYS = ('at', 'at_s', 'second', 'time', 'timestamp', 'moment',
                    'handed_at', 'handover_at', 'handoff_at', 'handoff_time',
                    'transfer_at', 'transfer_time', 'changed_at')
TRANSFER_FROM_KEYS = ('from_trays', 'source_trays', 'from_tray', 'from_tray_id',
                      'source_tray', 'source_tray_id', 'from', 'source')
TRANSFER_TO_KEYS = ('to_trays', 'destination_trays', 'target_trays', 'to_tray', 'to_tray_id',
                    'destination_tray', 'destination_tray_id', 'target_tray',
                    'target_tray_id', 'to', 'destination', 'dest', 'target')
TRANSFER_TRAY_KEYS = ('tray', 'tray_id')
TRANSFER_DECLARED_KEYS = ('trays', 'declared_trays')
TRANSFER_MOVE_KEYS = ('moves', 'movements', 'assignments', 'items', 'legs',
                      'pieces', 'piece_ids', 'workpieces', 'workpiece_ids',
                      'destinations')
TRANSFER_INVOLVED_KEYS = ('involved_trays', 'all_trays', 'related_trays')
TRANSFER_BATCH_KEYS = ('batch', 'batch_id', 'batch_no', 'transaction', 'transaction_id',
                       'tx', 'tx_id', 'transfer_id', 'group', 'group_id', 'handoff_id',
                       'handover_id', 'transfer_batch', 'handoff_ref')
TRANSFER_EXTRA_KEYS = {'note', 'label', 'name', 'kind'}

PIECE_ALLOWED = set(PIECE_ID_KEYS + PIECE_TRAY_KEYS + PIECE_SINCE_KEYS +
                    ('history', 'route', 'transfers', 'handoffs', 'handovers', 'movements'))
MOVE_ALLOWED = set(MOVE_PIECE_KEYS + MOVE_FROM_KEYS + MOVE_TO_KEYS)
TRANSFER_ALLOWED = ({'id', 'declared_trays', 'record_ids'} | set(TRANSFER_ID_KEYS) |
                    set(TRANSFER_AT_KEYS) |
                    set(TRANSFER_FROM_KEYS) | set(TRANSFER_TO_KEYS) |
                    set(TRANSFER_TRAY_KEYS) | set(TRANSFER_DECLARED_KEYS) |
                    set(TRANSFER_MOVE_KEYS) |
                    set(TRANSFER_INVOLVED_KEYS) | set(TRANSFER_BATCH_KEYS) |
                    set(MOVE_PIECE_KEYS) | TRANSFER_EXTRA_KEYS)


def first_value(row, keys):
    for key in keys:
        if key in row:
            return row[key], key
    return None, None


def allow_fields(row, allowed, label):
    if not isinstance(row, dict):
        raise Problem(f'{label}须为对象')
    unknown = set(row) - allowed
    if unknown:
        raise Problem(f'{label}包含未知字段：{sorted(unknown)[0]}')


def as_ref_list(value, label, valid=None):
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    result = []
    for item in values:
        if not isinstance(item, str):
            raise Problem(f'{label}须为料盘编号或编号数组')
        ref = ident(item, label)
        if valid is not None and ref not in valid:
            raise Problem(f'{label}引用未知料盘')
        result.append(ref)
    return result


def piece_ref(row, keys=MOVE_PIECE_KEYS):
    value, _ = first_value(row, keys)
    if value is None:
        raise Problem('交接去向缺少工件编号')
    return ident(value, '工件编号')


def parse_workpieces(value, trays, horizon):
    if value is None:
        return []
    if isinstance(value, dict):
        for envelope_key in ('workpieces', 'pieces', 'items'):
            if isinstance(value.get(envelope_key), list):
                value = value[envelope_key]
                break
    if isinstance(value, dict):
        raw_items = []
        for pid, config in value.items():
            if isinstance(config, str):
                raw_items.append({'id': pid, 'tray': config})
            elif isinstance(config, dict):
                raw_items.append({**config, 'id': pid})
            else:
                raise Problem('工件初始盘须为料盘编号或对象')
    else:
        raw_items = rows(value, '工件', 100000)
    if len(raw_items) > 100000:
        raise Problem('工件须有 0 至 100000 条记录')
    items = raw_items
    result = []
    for row in items:
        allow_fields(row, PIECE_ALLOWED, '工件')
        pid = piece_ref(row, PIECE_ID_KEYS)
        tray_value, _ = first_value(row, PIECE_TRAY_KEYS)
        if isinstance(tray_value, dict):
            initial = tray_value
            allow_fields(initial, {'tray', 'id', 'at', 'since', 'from_s'}, '工件初始盘')
            tray_value = initial.get('tray', initial.get('id'))
            since_value = first_value(initial, ('at', 'since', 'from_s'))[0]
        else:
            since_value = first_value(row, PIECE_SINCE_KEYS)[0]
        if tray_value is None:
            raise Problem('工件须填写初始盘')
        tray = ident(tray_value, '工件初始盘')
        if tray not in trays:
            raise Problem('工件初始盘引用未知料盘')
        since = 0 if since_value is None else number(since_value, 0, horizon, '工件初始时刻')
        result.append({'id': pid, 'initial_tray': tray, 'since': since})
    ids = [item['id'] for item in result]
    if len(ids) != len(set(ids)):
        raise Problem('工件编号重复')
    return sorted(result, key=lambda item: item['id'])


def _parse_move(raw, default_from, default_to, trays, piece_ids):
    if isinstance(raw, str):
        pid = ident(raw, '交接工件')
        source = default_from[0] if len(default_from) == 1 else None
        target = default_to[0] if len(default_to) == 1 else None
        if target is None:
            raise Problem('逐件去向须指定接盘')
        return {'piece': pid, 'from': source, 'to': target}
    allow_fields(raw, MOVE_ALLOWED, '逐件去向')
    pid = piece_ref(raw)
    from_value, _ = first_value(raw, MOVE_FROM_KEYS)
    to_value, _ = first_value(raw, MOVE_TO_KEYS)
    sources = as_ref_list(from_value, '交出盘', trays) if from_value is not None else []
    targets = as_ref_list(to_value, '接盘', trays) if to_value is not None else []
    source = sources[0] if sources else (default_from[0] if len(default_from) == 1 else None)
    target = targets[0] if targets else (default_to[0] if len(default_to) == 1 else None)
    if target is None:
        raise Problem('逐件去向须指定接盘')
    if pid not in piece_ids:
        raise Problem('交接记录引用未知工件')
    return {'piece': pid, 'from': source, 'to': target}


def transfers_from_piece_history(raw_pieces):
    """支持把交接按工件嵌套填写的资料形态。"""
    if not isinstance(raw_pieces, list):
        return []
    groups = {}
    result = []
    auto = 0
    history_keys = ('transfers', 'handoffs', 'handovers', 'movements', 'history', 'route')
    for piece_row in raw_pieces:
        if not isinstance(piece_row, dict):
            continue
        pid, _ = first_value(piece_row, PIECE_ID_KEYS)
        history, _ = first_value(piece_row, history_keys)
        if not isinstance(history, list):
            continue
        for move_row in history:
            auto += 1
            if isinstance(move_row, str):
                at_value, to_value = None, move_row
                move_row = {}
            elif isinstance(move_row, dict):
                at_value = first_value(move_row, TRANSFER_AT_KEYS)[0]
                to_value = first_value(move_row, MOVE_TO_KEYS)[0]
            else:
                continue
            tid = None
            if isinstance(move_row, dict):
                tid = first_value(move_row, ('id', 'handoff_id', 'handover_id', 'batch', 'batch_id'))[0]
            tid = tid or f'TR-HISTORY-{auto:04d}'
            if tid not in groups:
                group = {'id': tid, 'at': at_value, 'moves': []}
                groups[tid] = group
                result.append(group)
            group = groups[tid]
            move = {'piece': pid, 'to': to_value}
            from_value = first_value(move_row, MOVE_FROM_KEYS)[0] if isinstance(move_row, dict) else None
            if from_value is not None:
                move['from'] = from_value
            group['moves'].append(move)
            if group.get('at') is None:
                group['at'] = at_value
    return result


def parse_transfers(value, horizon, piece_ids, trays):
    if value is None:
        return []
    if isinstance(value, dict):
        for envelope_key in ('transfers', 'handoffs', 'handovers', 'items'):
            if isinstance(value.get(envelope_key), list):
                value = value[envelope_key]
                break
    if isinstance(value, dict):
        items = []
        for tid, config in value.items():
            if not isinstance(config, dict):
                raise Problem('交接记录须为对象')
            items.append({**config, 'id': tid})
    else:
        raw_rows = rows(value, '拆合交接', 100000)
        from .codec import canonical
        items = sorted(raw_rows, key=canonical)
    piece_set = set(piece_ids)
    result = []
    seen = set()
    for row in items:
        if not isinstance(row, dict):
            raise Problem('拆合交接须为对象')
        unknown = set(row) - TRANSFER_ALLOWED
        if unknown:
            raise Problem(f'拆合交接包含未知字段：{sorted(unknown)[0]}')
        tid_value, _ = first_value(row, TRANSFER_ID_KEYS)
        if tid_value is None:
            tid = f'TR-AUTO-{len(result) + 1:04d}'
        else:
            tid = ident(tid_value, '交接编号')
        batch_value, _ = first_value(row, TRANSFER_BATCH_KEYS)
        batch = ident(batch_value, '交接批次') if batch_value is not None else None
        if tid in seen:
            raise Problem('交接编号重复')
        seen.add(tid)
        at_value, at_key = first_value(row, TRANSFER_AT_KEYS)
        if at_value is None:
            raise Problem('拆合交接须填写交接时刻')
        at = number(at_value, 0, horizon, '交接时刻')

        header_from = []
        for key in TRANSFER_FROM_KEYS:
            if key in row:
                header_from.extend(as_ref_list(row[key], '交出盘', trays))
        header_to = []
        for key in TRANSFER_TO_KEYS:
            if key in row:
                header_to.extend(as_ref_list(row[key], '接盘', trays))
        declared_trays = []
        for key in TRANSFER_TRAY_KEYS:
            if key in row:
                header_from.extend(as_ref_list(row[key], '交出盘', trays))
        for key in TRANSFER_DECLARED_KEYS:
            if key in row:
                declared_trays.extend(as_ref_list(row[key], '交接料盘', trays))
        involved = []
        for key in TRANSFER_INVOLVED_KEYS:
            if key in row:
                involved.extend(as_ref_list(row[key], '交接相关料盘', trays))
        header_from = sorted(set(header_from))
        header_to = sorted(set(header_to))

        move_value, move_key = first_value(row, TRANSFER_MOVE_KEYS)
        if move_key == 'destinations' and isinstance(move_value, list) and all(
                isinstance(item, str) and item in trays for item in move_value):
            header_to.extend(ident(item, '接盘') for item in move_value)
            move_value = None
        moves = []
        if isinstance(move_value, dict):
            for pid, target in move_value.items():
                fake = {'piece': pid}
                if isinstance(target, dict):
                    fake.update(target)
                else:
                    fake['to'] = target
                moves.append(_parse_move(fake, header_from, header_to, trays, piece_set))
        elif isinstance(move_value, list):
            for raw_move in move_value:
                moves.append(_parse_move(raw_move, header_from, header_to, trays, piece_set))
        elif move_value is not None:
            raise Problem('逐件去向须为数组或工件到接盘的对象')

        if not moves and first_value(row, ('workpiece', 'piece', 'workpiece_id', 'piece_id'))[0] is not None:
            move_row = {key: row[key] for key in MOVE_ALLOWED if key in row}
            moves.append(_parse_move(move_row, header_from, header_to, trays, piece_set))

        # Header scalar/list destinations can also supply the target for moves.
        for move in moves:
            if move['from'] is None and len(header_from) == 1:
                move['from'] = header_from[0]
            if move['to'] is None and len(header_to) == 1:
                move['to'] = header_to[0]
            if move['piece'] not in piece_set:
                raise Problem('交接记录引用未知工件')
            if move['to'] not in trays:
                raise Problem('交接接盘引用未知料盘')
            if move['from'] is not None and move['from'] not in trays:
                raise Problem('交接交出盘引用未知料盘')

        note = row.get('note') or row.get('label') or row.get('name')
        if note is not None and not isinstance(note, str):
            raise Problem('交接备注须为字符串')
        transfer = {
            'id': tid,
            'at': at,
            'batch': batch,
            'source_trays': sorted(set(header_from) | {m['from'] for m in moves if m['from']}),
            'declared_trays': sorted(set(declared_trays)),
            'destination_trays': sorted(set(header_to) | {m['to'] for m in moves}),
            'involved_trays': sorted(set(header_from) | set(header_to) | set(declared_trays) |
                                     set(involved) | {m['from'] for m in moves if m['from']} |
                                     {m['to'] for m in moves}),
            'moves': sorted(moves, key=lambda m: (m['piece'], m['from'] or '', m['to'])),
        }
        if note is not None:
            transfer['note'] = note
        result.append(transfer)
    return _merge_batches(sorted(result, key=lambda item: item['id']))


def _merge_batches(transfers):
    grouped = {}
    order = []
    standalone = []
    for transfer in transfers:
        batch = transfer.get('batch')
        if not batch:
            standalone.append(transfer)
            continue
        if batch not in grouped:
            base = {key: value for key, value in transfer.items() if key != 'batch'}
            base['id'] = batch
            base['batch'] = batch
            base['moves'] = list(transfer['moves'])
            grouped[batch] = base
            order.append(batch)
        else:
            base = grouped[batch]
            if base['at'] != transfer['at']:
                raise Problem('同一交接批次必须使用同一交接时刻')
            base['moves'].extend(transfer['moves'])
            base['moves'] = sorted(base['moves'],
                                   key=lambda m: (m['piece'], m.get('from') or '', m['to']))
            for key in ('source_trays', 'declared_trays', 'destination_trays', 'involved_trays'):
                base[key] = sorted(set(base[key]) | set(transfer[key]))
    merged = standalone + [grouped[key] for key in order]
    return sorted(merged, key=lambda item: item['id'])


def occupancy_index(visits, unresolved):
    by_tray = defaultdict(list)
    for visit in visits.values():
        for item in visit:
            by_tray[item['tray']].append(item)
    for item in unresolved:
        by_tray[item['tray']].append(item)
    return by_tray


def occupied_trays(at, trays, occupancy):
    result = []
    for tray in trays:
        # 同秒顺序为：离位 -> 交接 -> 入位。因此 from == at 的入位在交接
        # 时尚未发生，to == at 的驻留已经结束。
        if any(item['from'] < at < item['to'] for item in occupancy.get(tray, [])):
            result.append(tray)
    return sorted(set(result))


def _issue(reason, transfer, **extra):
    return {'reason': reason, 'transfer': transfer['id'], 'at': transfer['at'],
            'sources': [transfer['id']], **extra}


def establish(workpieces, transfers, trays, visits, unresolved):
    """按秒应用交接，返回归属、寿命区间、退役盘和待核票据。"""
    current = {piece['id']: piece['initial_tray'] for piece in workpieces}
    since = {piece['id']: piece.get('since', 0) for piece in workpieces}
    timelines = {piece['id']: [] for piece in workpieces}
    retirements = {}
    tray_issues = defaultdict(list)
    records = []
    occupancy = occupancy_index(visits, unresolved)

    by_second = defaultdict(list)
    for transfer in sorted(transfers, key=lambda item: (item['at'], item['id'])):
        by_second[transfer['at']].append(transfer)

    for at in sorted(by_second):
        group = by_second[at]
        tray_uses = defaultdict(list)
        piece_uses = defaultdict(list)
        prepared = []

        for transfer in group:
            moves = []
            involved = set(transfer['involved_trays'])
            for move in transfer['moves']:
                source = move['from'] or current.get(move['piece'])
                resolved = {**move, 'from': source}
                moves.append(resolved)
                if source:
                    involved.add(source)
                involved.add(move['to'])
                piece_uses[move['piece']].append(transfer['id'])
            for tray in involved:
                tray_uses[tray].append(transfer['id'])
            prepared.append((transfer, moves, sorted(involved)))

        conflict_trays = {tray for tray, ids in tray_uses.items() if len(set(ids)) > 1}
        cross_pieces = {pid for pid, ids in piece_uses.items() if len(set(ids)) > 1}

        for transfer, moves, involved in prepared:
            reasons = []
            reason_details = {}
            conflicting = sorted({tid for tray in involved if tray in conflict_trays
                                  for tid in tray_uses[tray]})
            if len(conflicting) > 1:
                reasons.append('same_second')
                reason_details['conflicting_transfers'] = [tid for tid in conflicting
                                                           if tid != transfer['id']]
                reason_details['conflict_trays'] = [tray for tray in involved
                                                    if tray in conflict_trays]

            move_piece_ids = [move['piece'] for move in moves]
            duplicated = sorted({pid for pid in move_piece_ids if move_piece_ids.count(pid) > 1})
            if duplicated:
                reasons.append('duplicate_piece')
                reason_details['duplicate_pieces'] = duplicated
            cross_duplicated = sorted(pid for pid in cross_pieces if pid in set(move_piece_ids))
            if cross_duplicated:
                reasons.append('repeated_transfer')
                reason_details['repeated_pieces'] = cross_duplicated

            retired_involved = sorted(tray for tray in involved if tray in retirements)
            if retired_involved:
                reasons.append('retired_tray')
                reason_details['retired_trays'] = retired_involved

            occupied = occupied_trays(at, involved, occupancy)
            if occupied:
                reasons.append('occupied_slot')
                reason_details['occupied_trays'] = occupied

            mismatched = sorted({move['piece'] for move in moves
                                 if move['from'] is not None and
                                 current.get(move['piece']) != move['from']})
            if mismatched:
                reasons.append('ownership_mismatch')
                reason_details['mismatched_pieces'] = mismatched

            source_trays = set(transfer['source_trays']) | \
                {move['from'] for move in moves if move['from']}
            destination_set = {move['to'] for move in moves} | set(transfer['destination_trays'])
            # 泛写的 trays 可能是“涉及多盘”。纯接盘不要求清空原有工件；
            # 不是接盘的声明盘则按交出盘核对漏件。
            source_trays.update(tray for tray in transfer.get('declared_trays', [])
                                if tray not in destination_set)
            source_trays = sorted(source_trays)
            listed_by_source = defaultdict(list)
            for move in moves:
                if move['from']:
                    listed_by_source[move['from']].append(move['piece'])
            missing = set()
            for tray in source_trays:
                expected = {pid for pid, owner in current.items() if owner == tray}
                listed = set(listed_by_source.get(tray, []))
                missing.update(expected - listed)
            missing = sorted(missing)
            if missing:
                reasons.append('missing_piece')
                reason_details['missing_pieces'] = missing

            # 没有工件、也没有交出盘的空票据无法证明一次交接。
            if not moves and not source_trays:
                reasons.append('empty_transfer')

            effective = not reasons
            record = {
                **transfer,
                'moves': moves,
                'source_trays': source_trays,
                'involved_trays': involved,
                'state': 'effective' if effective else 'pending',
                'status': 'effective' if effective else 'pending',
                'result': 'effective' if effective else 'pending',
                'verdict': 'effective' if effective else 'pending',
                'effective': effective,
                'applied': effective,
                'accepted': effective,
                'pending': not effective,
                'ok': effective,
                'valid': effective,
                'reason': reasons[0] if reasons else None,
                'reasons': reasons,
                'reason_codes': reasons,
                'missing': 'missing_piece' in reasons,
                'duplicate': 'duplicate_piece' in reasons or 'repeated_transfer' in reasons,
                'retired_reuse': 'retired_tray' in reasons,
                'occupied': 'occupied_slot' in reasons,
                'conflict': 'same_second' in reasons,
                'needs_review': not effective,
                'quarantined': not effective,
                'issues': [{'reason': reason, **{k: v for k, v in reason_details.items()
                                                 if _reason_matches(reason, k)}}
                           for reason in reasons],
                **reason_details,
            }
            records.append(record)

            if effective:
                for move in moves:
                    pid = move['piece']
                    old_tray = current[pid]
                    timelines[pid].append({'tray': old_tray, 'from': since[pid], 'to': at,
                                           'transfer': transfer['id']})
                    current[pid] = move['to']
                    since[pid] = at
                for tray in source_trays:
                    if not any(owner == tray for owner in current.values()):
                        retirements[tray] = {'at': at, 'transfer': transfer['id']}
                record['retired_trays'] = sorted(tray for tray in source_trays
                                                 if tray in retirements and
                                                 retirements[tray]['transfer'] == transfer['id'])
            else:
                for tray in involved:
                    tray_issues[tray].append(_issue('transfer_pending', record,
                                                   transfer_id=transfer['id'],
                                                   reasons=reasons,
                                                   **reason_details))

    for piece in workpieces:
        pid = piece['id']
        timelines[pid].append({'tray': current[pid], 'from': since[pid], 'to': None,
                               'transfer': None})
        timelines[pid] = [segment for segment in timelines[pid]
                          if segment['to'] is None or segment['from'] < segment['to']]

    return {
        'current': current,
        'timelines': timelines,
        'retirements': retirements,
        'tray_issues': dict(tray_issues),
        'transfers': sorted(records, key=lambda item: (item['at'], item['id'])),
        'implicit': False,
    }


def _reason_matches(reason, detail_key):
    mapping = {
        'same_second': {'conflicting_transfers', 'conflict_trays'},
        'duplicate_piece': {'duplicate_pieces'},
        'repeated_transfer': {'repeated_pieces'},
        'retired_tray': {'retired_trays'},
        'occupied_slot': {'occupied_trays'},
        'ownership_mismatch': {'mismatched_pieces'},
        'missing_piece': {'missing_pieces'},
    }
    return detail_key in mapping.get(reason, set())
