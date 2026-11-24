from .archive import get_run, read_document
from .codec import canonical, decode, digest
from .errors import Problem
from .fields import number, obj
from .review_log import review_state


def current_dispatch(db, run_id):
    row = db.execute('SELECT content, content_hash FROM dispatch WHERE run_id=?', (run_id,)).fetchone()
    if row is None:
        return None
    content = decode(row['content'].encode('utf-8'))
    if digest(content) != row['content_hash']:
        raise Problem('交接件摘要不一致', 409)
    return {**content, 'dispatch_hash': row['content_hash']}


def prepare(db, run_id):
    entry = get_run(db, run_id)
    report = read_document(entry, 'analysis')
    state = review_state(db, run_id)
    included, excluded = [], []
    for tray in report['trays']:
        decision = state['current'].get(tray['id'])
        if tray['state'] == 'ready' and decision and decision['action'] == 'accept':
            included.append({'id': tray['id'], 'decision': decision, 'stages': tray['stages']})
        else:
            excluded.append({'id': tray['id'], 'state': tray['state'], 'decision': decision})
    return {'run': run_id, 'recipe': report['recipe'], 'engine': report['engine'], 'revision': state['revision'],
            'evidence_hash': entry['evidence_hash'], 'analysis_hash': entry['analysis_hash'],
            'included': included, 'excluded': excluded}


def freeze(store, run_id, value):
    obj(value, 'revision', '交接请求')
    expected = number(value['revision'], 0, 2**53 - 1, '签认版本')
    with store.connection(write=True) as db:
        current = current_dispatch(db, run_id)
        if current and current['revision'] == expected:
            return current
        if current:
            raise Problem('炉次交接件已冻结', 409)
        content = prepare(db, run_id)
        if content['revision'] != expected:
            raise Problem('交接预核已经变化，请重新预核', 409)
        if not content['included']:
            raise Problem('至少需要一盘通过签认', 409)
        content_hash = digest(content)
        db.execute('INSERT INTO dispatch VALUES(?,?,?)', (run_id, canonical(content), content_hash))
        return {**content, 'dispatch_hash': content_hash}
