from .calibration import parse_calibrations
from .fields import ident, number, rows, unique
from .gate_log import parse_events
from .lineage import parse_transfers, parse_workpieces, transfers_from_piece_history
from .plant import parse_slots
from .probe_log import parse_readings
from .recipe import parse_recipe


REQUIRED = ('id', 'horizon_s', 'max_gap_s', 'recipe', 'slots', 'trays',
            'events', 'readings', 'calibrations')
TOP_ALIASES = {
    'workpieces': ('workpieces', 'work_pieces', 'workpiece', 'pieces', 'piece',
                   'units', 'work_units', 'items', 'articles', 'parts', 'components',
                   'products'),
    'transfers': ('transfers', 'transfer_records', 'workpiece_transfers', 'piece_transfers',
                  'tray_changes', 'ownership_changes', 'movements', 'moves',
                  'handovers', 'handoffs', 'handover_records', 'handoff_records',
                  'lineage', 'lineages', 'lineage_events',
                  'exchanges', 'splits', 'merges', 'split_merges', 'split_merge'),
}


def normalize(value):
    if not isinstance(value, dict):
        from .errors import Problem
        raise Problem('炉次包须为 JSON 对象')
    wanted = set(REQUIRED) | {name for aliases in TOP_ALIASES.values() for name in aliases}
    unknown = set(value) - wanted
    missing = [key for key in REQUIRED if key not in value]
    if unknown or missing:
        from .errors import Problem
        if unknown:
            raise Problem(f'炉次包包含未知字段：{sorted(unknown)[0]}')
        raise Problem(f'炉次包缺少字段：{missing[0]}')

    run_id = ident(value['id'], '炉次编号')
    horizon = number(value['horizon_s'], 1, 86400, '炉次时域')
    max_gap = number(value['max_gap_s'], 1, horizon, '最大采样间隔')
    recipe = parse_recipe(value['recipe'], horizon)
    slots = parse_slots(value['slots'], recipe)
    trays = sorted(ident(tray, '料盘编号') for tray in rows(value['trays'], '料盘', 100, 1))
    unique(trays, '料盘编号')
    probes = {slot['probe'] for slot in slots}

    wp_names = [name for name in TOP_ALIASES['workpieces'] if name in value]
    if len(wp_names) > 1 and any(value[name] != value[wp_names[0]] for name in wp_names[1:]):
        from .errors import Problem
        raise Problem('工件别名字段内容不一致')
    wp_name = wp_names[0] if wp_names else None
    lineage_envelope = value.get('lineage') if isinstance(value.get('lineage'), dict) else None
    if wp_name:
        raw_workpieces = value[wp_name]
    elif lineage_envelope and any(key in lineage_envelope for key in ('workpieces', 'pieces')):
        wp_name = 'workpieces'
        raw_workpieces = lineage_envelope
    else:
        raw_workpieces = None
    workpieces = parse_workpieces(raw_workpieces, set(trays), horizon) if wp_name else []

    tr_names = [name for name in TOP_ALIASES['transfers'] if name in value]
    if len(tr_names) > 1 and any(value[name] != value[tr_names[0]] for name in tr_names[1:]):
        from .errors import Problem
        raise Problem('交接别名字段内容不一致')
    tr_name = tr_names[0] if tr_names else None
    if tr_name:
        raw_transfers = value[tr_name]
    else:
        raw_transfers = transfers_from_piece_history(raw_workpieces) if wp_name else None
    transfers = parse_transfers(raw_transfers, horizon, {p['id'] for p in workpieces},
                                set(trays)) if raw_transfers is not None else []

    source = {'id': run_id, 'horizon_s': horizon, 'max_gap_s': max_gap, 'recipe': recipe,
              'slots': slots, 'trays': trays,
              'events': parse_events(value['events'], horizon, set(trays), {slot['id'] for slot in slots}),
              'readings': parse_readings(value['readings'], horizon, probes),
              'calibrations': parse_calibrations(value['calibrations'], horizon, probes)}
    if wp_name:
        source['workpieces'] = workpieces
    if tr_name or (wp_name and raw_transfers):
        source['transfers'] = transfers
    return source
