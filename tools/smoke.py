import argparse
import copy
import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from hearthline.server import http_server
from hearthline.store import Store


WORKFLOWS = ('preview', 'archive', 'residency', 'collision', 'calibration', 'coverage',
             'trace', 'review', 'handoff', 'export', 'replay', 'web')


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
            assert response.status == status, (path, response.status, data[:500])
            return data if raw else json.loads(data)


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

    prepared = client(run + '/handoff')
    assert [entry['id'] for entry in prepared['included']] == ['A17']
    client(run + '/reviews/A24', {**review, 'revision': 1, 'action': 'hold'}, status=201)
    client(run + '/dispatch', {'revision': prepared['revision']}, status=409)
    frozen = client(run + '/dispatch', {'revision': 2})
    assert frozen == client(run + '/dispatch', {'revision': 2})
    assert frozen == client(run + '/handoff')
    client(run + '/reviews/A17', {**review, 'revision': 2}, status=409)
    yield 'handoff'

    downloaded = client(run + '/dispatch.json')
    records = list(csv.DictReader(io.StringIO(client(run + '/dispatch.csv', raw=True).decode('utf-8-sig'))))
    assert frozen == downloaded and len(records) == 3
    assert {(row['料盘'], row['交接摘要']) for row in records} == {('A17', frozen['dispatch_hash'])}
    yield 'export'

    rechecked = client(run + '/replay')
    assert all(rechecked[key] is True for key in ('ok', 'evidence_match', 'analysis_match', 'dispatch_match'))
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
