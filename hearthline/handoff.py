from .archive import get_run, read_document
from .codec import canonical, decode, digest
from .errors import Problem
from .fields import ident, number, obj, rows, unique
from .review_log import review_state


WHOLE_BATCH = 'whole-run'
PRECHECK_FIELDS = 'batch trays'
FREEZE_FIELDS = 'batch precheck_hash'


def _row_content(row):
    content = decode(row['content'].encode('utf-8'))
    if digest(content) != row['content_hash']:
        raise Problem('交接件摘要不一致', 409)
    return {**content, 'dispatch_hash': row['content_hash']}


def get_dispatch(db, run_id, batch_id):
    row = db.execute('SELECT content, content_hash FROM dispatch WHERE run_id=? AND batch_id=?',
                     (run_id, batch_id)).fetchone()
    return None if row is None else _row_content(row)


def whole_dispatch(db, run_id):
    return get_dispatch(db, run_id, WHOLE_BATCH)


def list_dispatches(db, run_id):
    rows = db.execute('SELECT batch_id, mode, content_hash FROM dispatch WHERE run_id=? ORDER BY rowid',
                      (run_id,)).fetchall()
    return [dict(row) for row in rows]


def dispatched_trays(db, run_id):
    rows = db.execute('SELECT tray, batch_id FROM dispatch_tray WHERE run_id=?', (run_id,)).fetchall()
    return {row['tray']: row['batch_id'] for row in rows}


def _accept_map(db, run_id, report, state):
    """生效的通过签认：证据齐备且当前签认动作为通过，按料盘给出依据。"""
    accepted = {}
    for tray in report['trays']:
        decision = state['current'].get(tray['id'])
        if tray['state'] == 'ready' and decision and decision['action'] == 'accept':
            accepted[tray['id']] = {'decision': decision, 'stages': tray['stages']}
    return accepted


def _entry_header(db, run_id):
    entry = get_run(db, run_id)
    report = read_document(entry, 'analysis')
    state = review_state(db, run_id)
    return entry, report, state


def prepare(db, run_id):
    """整炉视角的预核：列出生效的通过签认与暂不列入项。"""
    entry, report, state = _entry_header(db, run_id)
    taken = dispatched_trays(db, run_id)
    included, excluded = [], []
    for tray in report['trays']:
        decision = state['current'].get(tray['id'])
        if tray['id'] in taken:
            excluded.append({'id': tray['id'], 'state': 'dispatched', 'decision': decision,
                             'batch': taken[tray['id']]})
        elif tray['state'] == 'ready' and decision and decision['action'] == 'accept':
            included.append({'id': tray['id'], 'decision': decision, 'stages': tray['stages']})
        else:
            excluded.append({'id': tray['id'], 'state': tray['state'], 'decision': decision})
    return {'run': run_id, 'mode': 'batch', 'recipe': report['recipe'], 'engine': report['engine'],
            'revision': state['revision'], 'evidence_hash': entry['evidence_hash'],
            'analysis_hash': entry['analysis_hash'], 'included': included, 'excluded': excluded,
            'dispatches': list_dispatches(db, run_id), 'dispatched': taken}


def _selected_trays(value):
    obj(value, PRECHECK_FIELDS, '交接预核请求')
    batch_id = ident(value['batch'], '交接批号')
    if batch_id == WHOLE_BATCH:
        raise Problem('该批号为整炉交接保留，不能用于分批交接')
    picked = [ident(tray, '料盘编号') for tray in rows(value['trays'], '选盘', 100, 1)]
    unique(picked, '选盘')
    return batch_id, picked


def precheck(store, run_id, value):
    batch_id, picked = _selected_trays(value)
    with store.connection(write=True) as db:
        if whole_dispatch(db, run_id) is not None:
            raise Problem('该炉次已有整炉交接件，继续整炉冻结，不能分批交接', 409)
        entry, report, state = _entry_header(db, run_id)
        known = {tray['id']: tray for tray in report['trays']}
        unknown = [tray for tray in picked if tray not in known]
        if unknown:
            raise Problem(f"选盘包含未登记料盘：{'、'.join(unknown)}", 404)
        taken = dispatched_trays(db, run_id)
        occupied = sorted({tray for tray in picked if tray in taken})
        if occupied:
            raise Problem(f"选盘已随其他批次交接：{'、'.join(occupied)}", 409)
        accepted = _accept_map(db, run_id, report, state)
        missing = sorted({tray for tray in picked if tray not in accepted})
        if missing:
            raise Problem(f"选盘须均有生效的通过签认：{'、'.join(missing)}", 409)
        # 预核只固化所选盘及其各自生效的通过签认代次；其他盘的补签不影响本预核。
        included = [{'id': tray, 'decision': accepted[tray]['decision'],
                     'decision_revision': accepted[tray]['decision']['revision'],
                     'stages': known[tray]['stages']} for tray in picked]
        excluded = [{'id': tray['id'], 'state': 'dispatched' if tray['id'] in taken else tray['state']}
                    for tray in report['trays'] if tray['id'] not in set(picked)]
        content = {'run': run_id, 'mode': 'batch', 'batch': batch_id, 'recipe': report['recipe'],
                   'engine': report['engine'],
                   'evidence_hash': entry['evidence_hash'], 'analysis_hash': entry['analysis_hash'],
                   'included': included, 'excluded': excluded}
        precheck_hash = digest(content)
        db.execute(
            '''INSERT INTO dispatch_precheck(run_id, batch_id, precheck_hash, revision, trays, content)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(run_id, batch_id) DO UPDATE SET precheck_hash=excluded.precheck_hash,
                   revision=excluded.revision, trays=excluded.trays, content=excluded.content,
                   updated=CURRENT_TIMESTAMP''',
            (run_id, batch_id, precheck_hash, state['revision'], canonical(picked), canonical(content)))
        return {**content, 'precheck_hash': precheck_hash}


def _validate_selection(picked, prepared, accepted, taken):
    """确认时复核：所选盘未交接，且各盘生效通过签认仍是预核所用那条（同代次）。"""
    conflict = sorted({tray for tray in picked if tray in taken})
    if conflict:
        raise Problem(f"选盘已随其他批次交接：{'、'.join(conflict)}", 409)
    expected = {entry['id']: entry['decision_revision'] for entry in prepared['included']}
    for tray in picked:
        if tray not in accepted:
            raise Problem(f'料盘 {tray} 已无生效的通过签认，请重新预核', 409)
        if accepted[tray]['decision']['revision'] != expected[tray]:
            raise Problem(f'料盘 {tray} 的通过签认已更新，请重新预核', 409)


def freeze(store, run_id, value):
    obj(value, FREEZE_FIELDS, '交接请求')
    batch_id = ident(value['batch'], '交接批号')
    if batch_id == WHOLE_BATCH:
        raise Problem('该批号为整炉交接保留，请走整炉冻结入口')
    precheck_hash = value['precheck_hash']
    if (not isinstance(precheck_hash, str) or len(precheck_hash) != 64
            or any(char not in '0123456789abcdef' for char in precheck_hash)):
        raise Problem('预核摘要须为 64 位十六进制字符串')
    with store.connection(write=True) as db:
        if whole_dispatch(db, run_id) is not None:
            raise Problem('该炉次已有整炉交接件，继续整炉冻结，不能分批交接', 409)
        stored = db.execute(
            'SELECT precheck_hash, trays, content FROM dispatch_precheck WHERE run_id=? AND batch_id=?',
            (run_id, batch_id)).fetchone()
        if stored is None:
            raise Problem('该批号还没有预核，请先预核', 409)
        current = get_dispatch(db, run_id, batch_id)
        if current is not None:
            if current['precheck_hash'] == precheck_hash:
                return current
            raise Problem('该批号已冻结，沿用批号改选盘或换新预核均拒绝', 409)
        if stored['precheck_hash'] != precheck_hash:
            raise Problem('预核已经变化，请按最新预核重新确认', 409)
        prepared = decode(stored['content'].encode('utf-8'))
        entry, report, state = _entry_header(db, run_id)
        accepted = _accept_map(db, run_id, report, state)
        taken = dispatched_trays(db, run_id)
        picked = decode(stored['trays'].encode('utf-8'))
        _validate_selection(picked, prepared, accepted, taken)
        # 冻结件沿用预核快照（含本批采用的签认与各盘证据），追加预核摘要后不可变。
        content = {**prepared, 'precheck_hash': precheck_hash}
        content_hash = digest(content)
        db.execute('INSERT INTO dispatch(run_id, batch_id, mode, content, content_hash) VALUES(?,?,?,?,?)',
                   (run_id, batch_id, 'batch', canonical(content), content_hash))
        db.executemany('INSERT INTO dispatch_tray(run_id, tray, batch_id) VALUES(?,?,?)',
                       ((run_id, tray, batch_id) for tray in picked))
        return {**content, 'dispatch_hash': content_hash}


def freeze_whole(store, run_id, value):
    """整炉冻结：沿用旧版 revision 乐观锁，冻结后整炉（含当时未入件盘）全部停签。"""
    obj(value, 'revision', '整炉交接请求')
    expected = number(value['revision'], 0, 2**53 - 1, '签认版本')
    with store.connection(write=True) as db:
        current = whole_dispatch(db, run_id)
        if current and current['revision'] == expected:
            return current
        if current:
            raise Problem('炉次交接件已冻结', 409)
        if db.execute('SELECT 1 FROM dispatch WHERE run_id=?', (run_id,)).fetchone():
            raise Problem('该炉次已存在分批交接件，不能再整炉冻结', 409)
        content = prepare(db, run_id)
        if content['revision'] != expected:
            raise Problem('交接预核已经变化，请重新预核', 409)
        if not content['included']:
            raise Problem('至少需要一盘通过签认', 409)
        content.pop('dispatches', None)
        content.pop('dispatched', None)
        content = {**content, 'mode': 'whole', 'batch': WHOLE_BATCH, 'precheck_hash': None}
        content_hash = digest(content)
        db.execute('INSERT INTO dispatch(run_id, batch_id, mode, content, content_hash) VALUES(?,?,?,?,?)',
                   (run_id, WHOLE_BATCH, 'whole', canonical(content), content_hash))
        db.executemany(
            'INSERT OR IGNORE INTO dispatch_tray(run_id, tray, batch_id) VALUES(?,?,?)',
            ((run_id, tray['id'], WHOLE_BATCH) for tray in
             read_document(get_run(db, run_id), 'analysis')['trays']))
        return {**content, 'dispatch_hash': content_hash}
