from pathlib import Path
from urllib.parse import parse_qs

from . import archive, evidence, handoff, replay, review_log, workbench
from .errors import Problem
from .export import as_csv
from .fields import ident
from .response import Reply, json_reply


ROOT = Path(__file__).resolve().parents[1]
API = '/api/hearth/'


def dispatch(store, method, path, query, body):
    if not path.startswith(API):
        raise Problem('没有找到该入口', 404)
    parts = path[len(API):].split('/')
    if method == 'GET' and parts == ['example']:
        return Reply((ROOT / 'examples' / 'alder.json').read_bytes(), 'application/json; charset=utf-8')
    if method == 'POST' and parts == ['preview']:
        _, report = archive.preview(body())
        return json_reply(report)
    if parts == ['runs'] and method == 'POST':
        result = archive.receive(store, body())
        return json_reply(result, 201 if result['created'] else 200)
    if parts == ['runs'] and method == 'GET':
        params = parse_qs(query, keep_blank_values=True)
        raw = params.get('offset', ['0'])
        if len(raw) != 1 or len(raw[0]) > 6 or not raw[0].isascii() or not raw[0].isdigit():
            raise Problem('目录偏移须为非负整数')
        with store.connection() as db:
            return json_reply(archive.list_runs(db, int(raw[0])))
    if len(parts) < 2 or parts[0] != 'runs':
        raise Problem('没有找到该入口', 404)
    run_id = ident(parts[1], '炉次编号')
    action = parts[2:]
    if method == 'POST' and len(action) == 2 and action[0] == 'reviews':
        return json_reply(review_log.append_review(store, run_id, action[1], body()), 201)
    if method == 'POST' and action == ['handoff', 'precheck']:
        return json_reply(handoff.precheck(store, run_id, body()), 201)
    if method == 'POST' and action == ['dispatch']:
        return json_reply(handoff.freeze_whole(store, run_id, body()))
    if method == 'POST' and action == ['batches']:
        return json_reply(handoff.freeze(store, run_id, body()))
    if method != 'GET':
        raise Problem('没有找到该入口', 404)
    with store.connection() as db:
        return read_run(db, run_id, action)


def _download(db, run_id, batch_id, suffix):
    content = handoff.get_dispatch(db, run_id, batch_id)
    if content is None:
        raise Problem('该交接件尚未冻结', 404)
    label = handoff.WHOLE_BATCH if batch_id == handoff.WHOLE_BATCH else batch_id
    attachment = {'Content-Disposition': f'attachment; filename="{run_id}-{label}-{suffix}"'}
    if suffix == 'csv':
        return Reply(as_csv(content), 'text/csv; charset=utf-8', headers=attachment)
    return json_reply(content, **attachment)


def read_run(db, run_id, action):
    if not action:
        return json_reply(workbench.load(db, run_id))
    if action == ['source']:
        return json_reply(archive.read_document(archive.get_run(db, run_id), 'evidence'))
    if len(action) == 2 and action[0] == 'trace':
        row = archive.get_run(db, run_id)
        return json_reply(evidence.trace_tray(archive.read_document(row, 'analysis'),
                                             archive.read_document(row, 'evidence'), action[1]))
    if action == ['handoff']:
        whole = handoff.whole_dispatch(db, run_id)
        return json_reply(whole if whole is not None else handoff.prepare(db, run_id))
    if action == ['replay']:
        return json_reply(replay.verify(db, run_id))
    if action in (['dispatch.json'], ['dispatch.csv']):
        return _download(db, run_id, handoff.WHOLE_BATCH, action[0].split('.')[1])
    if len(action) == 3 and action[0] == 'batches':
        batch_id = ident(action[1], '交接批号')
        suffix = action[2]
        if suffix not in ('json', 'csv'):
            raise Problem('没有找到该入口', 404)
        return _download(db, run_id, batch_id, suffix)
    raise Problem('没有找到该入口', 404)
