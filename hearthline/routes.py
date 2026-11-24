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
    if method == 'POST' and action == ['dispatch']:
        return json_reply(handoff.freeze(store, run_id, body()))
    if method != 'GET':
        raise Problem('没有找到该入口', 404)
    with store.connection() as db:
        return read_run(db, run_id, action)


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
        return json_reply(handoff.current_dispatch(db, run_id) or handoff.prepare(db, run_id))
    if action == ['replay']:
        return json_reply(replay.verify(db, run_id))
    if action in (['dispatch.json'], ['dispatch.csv']):
        content = handoff.current_dispatch(db, run_id)
        if content is None:
            raise Problem('炉次尚未冻结交接件', 404)
        attachment = {'Content-Disposition': f'attachment; filename="{run_id}-{action[0]}"'}
        if action == ['dispatch.csv']:
            return Reply(as_csv(content), 'text/csv; charset=utf-8', headers=attachment)
        return json_reply(content, **attachment)
    raise Problem('没有找到该入口', 404)
