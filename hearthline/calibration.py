from collections import defaultdict

from .errors import Problem
from .fields import ident, number, obj, rows, unique


def parse_calibrations(value, horizon, probes):
    windows = []
    for row in rows(value, '校准凭证', 512):
        obj(row, 'id probe from to offset_tenth', '校准凭证')
        probe = ident(row['probe'], '校准测点')
        start = number(row['from'], 0, horizon, '校准开始秒')
        end = number(row['to'], 0, horizon, '校准结束秒')
        if probe not in probes or start >= end:
            raise Problem('校准凭证须引用已登记测点并具有正时长')
        windows.append({'id': ident(row['id'], '校准编号'), 'probe': probe, 'from': start, 'to': end,
                        'offset_tenth': number(row['offset_tenth'], -1000, 1000, '校准偏移')})
    unique([row['id'] for row in windows], '校准编号')
    windows.sort(key=lambda row: (row['probe'], row['from']))
    for left, right in zip(windows, windows[1:]):
        if left['probe'] == right['probe'] and left['to'] > right['from']:
            raise Problem('同一测点的校准生效期间重叠')
    return windows


def apply_calibrations(segments, windows):
    by_probe = defaultdict(list)
    for window in windows:
        by_probe[window['probe']].append(window)
    result = {}
    for probe, intervals in segments.items():
        active = by_probe[probe]
        index = 0
        tempered = []
        for interval in intervals:
            if interval['reason']:
                tempered.append(interval)
                continue
            cursor = interval['from']
            while cursor < interval['to']:
                while index < len(active) and active[index]['to'] <= cursor:
                    index += 1
                window = active[index] if index < len(active) else None
                if window and window['from'] <= cursor:
                    end = min(interval['to'], window['to'])
                    tempered.append({**interval, 'from': cursor, 'to': end, 'calibration': window['id'],
                                     'tenth': interval['tenth'] + window['offset_tenth']})
                else:
                    end = min(interval['to'], window['from']) if window else interval['to']
                    tempered.append({**interval, 'from': cursor, 'to': end,
                                     'reason': 'uncalibrated', 'tenth': None})
                cursor = end
        result[probe] = tempered
    return result
