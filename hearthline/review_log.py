from .archive import get_run, read_document
from .errors import Problem
from .fields import ident, number, obj, text


def review_state(db, run_id):
    events = [dict(row) for row in db.execute(
        'SELECT revision, tray, action, reviewer, note FROM review_event WHERE run_id=? ORDER BY revision', (run_id,))]
    return {'revision': events[-1]['revision'] if events else 0, 'events': events,
            'current': {event['tray']: event for event in events}}


def append_review(store, run_id, tray_id, value):
    obj(value, 'revision action reviewer note', '签认记录')
    ident(tray_id, '料盘编号')
    expected = number(value['revision'], 0, 2**53 - 1, '签认版本')
    action = value['action']
    if action not in ('accept', 'hold'):
        raise Problem('签认操作仅接受 accept 或 hold')
    reviewer = text(value['reviewer'], '复核人', 40)
    note = text(value['note'], '依据')
    with store.connection(write=True) as db:
        report = read_document(get_run(db, run_id), 'analysis')
        tray = next((tray for tray in report['trays'] if tray['id'] == tray_id), None)
        if tray is None:
            raise Problem('没有找到该料盘', 404)
        if db.execute('SELECT 1 FROM dispatch WHERE run_id=?', (run_id,)).fetchone():
            raise Problem('炉次交接件已冻结', 409)
        state = review_state(db, run_id)
        if expected != state['revision']:
            raise Problem('签认记录已经变化，请刷新后重试', 409)
        if action == 'accept' and tray['state'] != 'ready':
            raise Problem('路线或热历证据未就绪，当前不能签认通过', 409)
        revision = expected + 1
        db.execute('INSERT INTO review_event VALUES(?,?,?,?,?,?)', (run_id, revision, tray_id, action, reviewer, note))
        return {'revision': revision, 'tray': tray_id, 'action': action, 'reviewer': reviewer, 'note': note}
