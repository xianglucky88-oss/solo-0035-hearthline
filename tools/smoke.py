import argparse
import copy
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier, Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from hearthline.server import http_server
from hearthline.store import Store


WORKFLOWS = ('preview', 'archive', 'residency', 'collision', 'calibration', 'coverage',
             'trace', 'review', 'handoff', 'batch', 'export', 'replay', 'web')


class Client:
    def __init__(self, port):
        self.origin = f'http://127.0.0.1:{port}'

    def __call__(self, path, payload=None, status=200, raw=False):
        url = self.origin + (path if path.startswith('/') else '/api/hearth/' + path)
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        request = Request(url, data=data, headers={'Content-Type': 'application/json'})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            if response.status != status:
                raise AssertionError((path, response.status, data[:500]))
            return data if raw else json.loads(data)


def multi_run(run_id, trays):
    """构造全部料盘证据齐备、互不撞占的合成炉次，用于分批交接。"""
    slots = [
        {'id': 'P1', 'zone': 'warm', 'probe': 'T-P1'},
        {'id': 'S1', 'zone': 'soak', 'probe': 'T-S1'},
        {'id': 'F1', 'zone': 'finish', 'probe': 'T-F1'},
    ]
    recipe = {'id': 'R-multi', 'stages': [
        {'zone': 'warm', 'label': '预热', 'min_tenth': 5000, 'max_tenth': 5200, 'min_contiguous_s': 12},
        {'zone': 'soak', 'label': '保温', 'min_tenth': 6900, 'max_tenth': 7100, 'min_contiguous_s': 15},
        {'zone': 'finish', 'label': '均温', 'min_tenth': 3300, 'max_tenth': 3500, 'min_contiguous_s': 8}]}
    schedule = {'P1': (0, 20), 'S1': (25, 45), 'F1': (50, 70)}
    events = []
    for index, tray in enumerate(trays):
        shift = index * 80
        for slot, (start, end) in schedule.items():
            events += [
                {'id': f'{tray}-{slot}-in', 'tray': tray, 'slot': slot, 'at': start + shift, 'kind': 'enter'},
                {'id': f'{tray}-{slot}-out', 'tray': tray, 'slot': slot, 'at': end + shift, 'kind': 'leave'}]
    horizon = 80 * len(trays) + 80
    readings, calibrations = [], []
    for probe, tenth in (('T-P1', 5100), ('T-S1', 7000), ('T-F1', 3400)):
        for at in range(0, horizon + 1, 5):
            readings.append({'id': f'{probe}-{at:04d}', 'probe': probe, 'at': at, 'tenth': tenth, 'valid': True})
        calibrations.append({'id': f'{probe}-c1', 'probe': probe, 'from': 0, 'to': horizon, 'offset_tenth': 0})
    return {'id': run_id, 'horizon_s': horizon, 'max_gap_s': 10, 'recipe': recipe, 'slots': slots,
            'trays': trays, 'events': events, 'readings': readings, 'calibrations': calibrations}


def check(client):
    source = client('example')
    run = f'runs/{source["id"]}'
    report = client('preview', source)
    assert client('runs') == [] and len(report['trays']) == 6
    bad = copy.deepcopy(source)
    next(window for window in bad['calibrations'] if window['id'] == 'S1-c2')['from'] = 41
    assert client('preview', bad, status=400)['error']
    yield 'preview'

    receipt = client('runs', source, status=201)
    assert receipt['created'] and client('runs')[0]['id'] == source['id']
    shuffled = {**source, 'events': source['events'][::-1], 'readings': source['readings'][::-1]}
    assert client('runs', shuffled) == {**receipt, 'created': False}
    client('runs', {**source, 'max_gap_s': 9}, status=409)
    yield 'archive'

    result = client(run)['report']
    trays = {tray['id']: tray for tray in result['trays']}
    assert [stage['from'] for stage in trays['A17']['stages']] == [0, 25, 60]
    assert [item['reason'] for item in trays['A68']['issues']] == ['gate_open', 'itinerary']
    yield 'residency'

    [collision] = result['conflicts']
    assert collision['trays'] == ['A31', 'A42'] and (collision['from'], collision['to']) == (18, 22)
    assert all(trays[tray]['state'] == 'blocked' for tray in collision['trays'])
    suspected = copy.deepcopy(source)
    next(event for event in suspected['events'] if event['id'] == 'A68-F1-in')['at'] = 130
    [possible] = [item for item in client('preview', suspected)['conflicts'] if item['tentative']]
    assert possible['trays'] == ['A55', 'A68'] and (possible['from'], possible['to']) == (130, 138)
    yield 'collision'

    trace = client(run + '/trace/A17')
    heat = trace['tray']['stages'][1]
    split = [item for item in heat['slices'] if item['from'] == 42]
    assert split[0]['calibration'] == 'S1-c2' and split[0]['tenth'] == 7130 and split[0]['to'] == 45
    assert heat['longest_s'] == 17 and heat['known_s'] == 35
    yield 'calibration'

    inspect = client(run + '/trace/A24')['tray']['stages'][1]
    assert inspect['duration_s'] == 37 and inspect['known_s'] == 8
    assert {part['reason'] for part in inspect['slices']} == {None, 'sample_gap', 'sample_invalid', 'uncalibrated'}
    assert {tray_id: trays[tray_id]['state'] for tray_id in ('A17', 'A24', 'A55')} == {
        'A17': 'ready', 'A24': 'inspect', 'A55': 'inspect'}
    assert trays['A55']['stages'][1]['state'] == 'short'
    yield 'coverage'

    overlap = client(run + '/trace/A31')
    assert {'A31', 'A42'} == {event['tray'] for event in overlap['events']}
    assert [window['id'] for window in trace['calibrations'] if window['probe'] == 'T-S1'] == ['S1-c1', 'S1-c2']
    assert client(run + '/trace/UNKNOWN', status=404)['error']
    yield 'trace'

    review = {'revision': 0, 'action': 'accept', 'reviewer': '孟工', 'note': '核对三个阶段的证据。'}
    client(run + '/reviews/A24', review, status=409)
    assert client(run + '/reviews/A17', review, status=201)['revision'] == 1
    client(run + '/reviews/A17', {**review, 'action': 'hold'}, status=409)
    assert client(run)['reviews']['current']['A17']['action'] == 'accept'
    yield 'review'

    # 整炉冻结沿用旧入口与 revision 乐观锁；冻结后整炉（含未入件盘）停止签认。
    prepared = client(run + '/handoff')
    assert [entry['id'] for entry in prepared['included']] == ['A17']
    client(run + '/reviews/A24', {**review, 'revision': 1, 'action': 'hold'}, status=201)
    client(run + '/dispatch', {'revision': prepared['revision']}, status=409)
    frozen = client(run + '/dispatch', {'revision': 2})
    assert frozen['mode'] == 'whole' and frozen['batch'] == 'whole-run'
    assert frozen == client(run + '/dispatch', {'revision': 2})
    assert frozen == client(run + '/handoff')
    client(run + '/reviews/A17', {**review, 'revision': 2}, status=409)
    client(run + '/reviews/A55', {**review, 'revision': 2, 'action': 'hold'}, status=409)
    # 整炉冻结的炉次不能再分批交接。
    client(run + '/handoff/precheck', {'batch': 'B-9', 'trays': ['A17']}, status=409)
    client(run + '/batches', {'batch': 'B-9', 'precheck_hash': '0' * 64}, status=409)
    yield 'handoff'

    # ---- 分批交接：独立炉次，三个料盘均可签认通过 ----
    multi_source = multi_run('MULTI-9', ['B1', 'B2', 'B3'])
    multi = f'runs/{multi_source["id"]}'
    assert all(tray['state'] == 'ready' for tray in client('preview', multi_source)['trays'])
    client('runs', multi_source, status=201)
    for index, tray in enumerate(('B1', 'B2', 'B3'), start=1):
        client(multi + f'/reviews/{tray}', {**review, 'revision': index - 1}, status=201)
    projection = client(multi + '/handoff')
    assert [entry['id'] for entry in projection['included']] == ['B1', 'B2', 'B3']
    assert projection['dispatches'] == [] and projection['dispatched'] == {}

    # 预核只接受有生效通过签认且未交接的盘。
    client(multi + '/handoff/precheck', {'batch': 'BX', 'trays': ['B1', 'NOPE']}, status=404)
    client(multi + '/handoff/precheck', {'batch': 'BX', 'trays': ['B1', 'B1']}, status=400)
    pre_one = client(multi + '/handoff/precheck', {'batch': 'B-ONE', 'trays': ['B1']}, status=201)
    assert [entry['id'] for entry in pre_one['included']] == ['B1']
    assert pre_one['precheck_hash'] and pre_one['mode'] == 'batch'
    pre_two = client(multi + '/handoff/precheck', {'batch': 'B-TWO', 'trays': ['B2', 'B3']}, status=201)

    # 其他盘补签（B2 暂缓再通过）不影响 B-ONE 的预核；B1 若暂缓再通过则须重新预核。
    client(multi + '/reviews/B2', {**review, 'revision': 3, 'action': 'hold'}, status=201)
    client(multi + '/reviews/B2', {**review, 'revision': 4, 'action': 'accept'}, status=201)
    assert client(multi + '/handoff/precheck', {'batch': 'B-ONE', 'trays': ['B1']}, status=201)['precheck_hash'] \
        == pre_one['precheck_hash']
    client(multi + '/reviews/B1', {**review, 'revision': 5, 'action': 'hold'}, status=201)
    client(multi + '/reviews/B1', {**review, 'revision': 6, 'action': 'accept'}, status=201)
    client(multi + '/batches', {'batch': 'B-ONE', 'precheck_hash': pre_one['precheck_hash']}, status=409)
    pre_one = client(multi + '/handoff/precheck', {'batch': 'B-ONE', 'trays': ['B1']}, status=201)

    # 无预核、错预核摘要、空选盘均拒绝。
    client(multi + '/batches', {'batch': 'B-GHOST', 'precheck_hash': '0' * 64}, status=409)
    client(multi + '/batches', {'batch': 'B-ONE', 'precheck_hash': 'f' * 64}, status=409)

    # 并发两批争同一盘 B2：只许一批成功；败批独有的 B3 不被占用。
    rival = client(multi + '/handoff/precheck', {'batch': 'B-RIVAL', 'trays': ['B2']}, status=201)
    # 冻结前再做一个同盘、同内容的备用预核，供“同批号换新预核”拒绝断言使用。
    spare = client(multi + '/handoff/precheck', {'batch': 'B-SPARE', 'trays': ['B1']}, status=201)
    barrier = Barrier(2)
    outcomes = {}

    def freeze_batch(batch, token, key):
        barrier.wait()
        try:
            outcomes[key] = client(multi + '/batches', {'batch': batch, 'precheck_hash': token})
        except AssertionError as exc:
            outcomes[key] = exc.args[0][1]
        except BaseException as exc:  # pragma: no cover - 暴露并发线程内的真实错误
            outcomes[key] = f'ERROR: {type(exc).__name__}: {exc}'

    threads = [
        Thread(target=freeze_batch, args=('B-TWO', pre_two['precheck_hash'], 'two')),
        Thread(target=freeze_batch, args=('B-RIVAL', rival['precheck_hash'], 'rival'))]
    for worker in threads:
        worker.start()
    for worker in threads:
        worker.join()
    assert set(outcomes) == {'two', 'rival'}, outcomes
    statuses = {key: (200 if isinstance(value, dict) else value) for key, value in outcomes.items()}
    assert sorted(statuses.values()) == [200, 409], outcomes
    winner = next(key for key, code in statuses.items() if code == 200)
    after = client(multi + '/handoff')
    if winner == 'two':
        # B-TWO 拿到 B2、B3；败批 B-RIVAL 不落任何盘，B3 已被占用。
        assert after['dispatched'] == {'B2': 'B-TWO', 'B3': 'B-TWO'}
        client(multi + '/batches', {'batch': 'B-RIVAL', 'precheck_hash': rival['precheck_hash']}, status=409)
    else:
        # B-RIVAL 只拿到 B2；败批 B-TWO 独有的 B3 不被占用，可另批交接。
        assert after['dispatched'] == {'B2': 'B-RIVAL'}
        client(multi + '/batches', {'batch': 'B-TWO', 'precheck_hash': pre_two['precheck_hash']}, status=409)
        b3 = client(multi + '/handoff/precheck', {'batch': 'B-THREE', 'trays': ['B3']}, status=201)
        client(multi + '/batches', {'batch': 'B-THREE', 'precheck_hash': b3['precheck_hash']})

    # B1 单独成批交接；同批号 + 原预核重交返回原件，配另一预核（即便内容相同）一律拒绝。
    one = client(multi + '/batches', {'batch': 'B-ONE', 'precheck_hash': pre_one['precheck_hash']})
    assert [entry['id'] for entry in one['included']] == ['B1']
    again = client(multi + '/batches', {'batch': 'B-ONE', 'precheck_hash': pre_one['precheck_hash']})
    assert again == one
    client(multi + '/batches', {'batch': 'B-ONE', 'precheck_hash': spare['precheck_hash']}, status=409)

    # 每盘只能交接一次，交接后停止追加签认；未交接盘在本场景已全部交接。
    client(multi + '/reviews/B1', {**review, 'revision': 6, 'action': 'hold'}, status=409)
    final = client(multi + '/handoff')
    assert set(final['dispatched']) == {'B1', 'B2', 'B3'}
    assert final['included'] == []
    yield 'batch'

    # ---- 下载：只列本批盘，批号进文件名；整炉件走旧路径 ----
    whole_json = client(run + '/dispatch.json')
    whole_rows = list(csv.DictReader(io.StringIO(client(run + '/dispatch.csv', raw=True).decode('utf-8-sig'))))
    assert whole_json == frozen and {row['料盘'] for row in whole_rows} == {'A17'}
    batch_json = client(multi + '/batches/B-ONE/json')
    assert [entry['id'] for entry in batch_json['included']] == ['B1']
    batch_rows = list(csv.DictReader(io.StringIO(
        client(multi + '/batches/B-ONE/csv', raw=True).decode('utf-8-sig'))))
    assert {row['料盘'] for row in batch_rows} == {'B1'} and all(row['批号'] == 'B-ONE' for row in batch_rows)
    assert client(multi + '/batches/B-GHOST/json', status=404)['error']
    yield 'export'

    # 复算沿用原始炉次证据及各批采用的签认；补签和后续交接不影响旧件。
    rechecked = client(run + '/replay')
    assert all(rechecked[key] is True for key in ('ok', 'evidence_match', 'analysis_match', 'dispatch_match'))
    multi_check = client(multi + '/replay')
    assert multi_check['ok'] and multi_check['dispatch_match'] is True
    assert all(item['match'] for item in multi_check['dispatch_checks'])
    assert client(run + '/source')['id'] == source['id']
    yield 'replay'

    assert '连续炉料盘热历核对台' in client('/', raw=True).decode('utf-8')
    assert b'connectImport' in client('/main.mjs', raw=True)
    assert b'.timeline' in client('/timeline.css', raw=True)
    client('/schema.sql', status=404)
    yield 'web'


def main():
    parser = argparse.ArgumentParser(description='使用合成炉次验证本机生产工作流')
    parser.add_argument('--through', choices=WORKFLOWS, default=WORKFLOWS[-1])
    args = parser.parse_args()
    with TemporaryDirectory(prefix='hearthline-smoke-') as directory:
        store = Store(Path(directory) / 'smoke.sqlite')
        with http_server(0, store) as server:
            worker = Thread(target=server.serve_forever, kwargs={'poll_interval': .02}, daemon=True)
            worker.start()
            try:
                for workflow in check(Client(server.server_port)):
                    print(f'{workflow} OK')
                    if workflow == args.through:
                        break
            finally:
                server.shutdown()
                worker.join(5)


if __name__ == '__main__':
    main()
