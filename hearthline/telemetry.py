from collections import defaultdict


def probe_segments(readings, max_gap):
    grouped = defaultdict(list)
    for reading in readings:
        grouped[reading['probe']].append(reading)
    result = {}
    for probe, items in grouped.items():
        intervals = []
        for left, right in zip(items, items[1:]):
            reason = None
            if right['at'] - left['at'] > max_gap:
                reason = 'sample_gap'
            elif not left['valid'] or not right['valid']:
                reason = 'sample_invalid'
            intervals.append({'from': left['at'], 'to': right['at'], 'sources': [left['id'], right['id']],
                              'tenth': left['tenth'] if reason is None else None,
                              'reason': reason, 'calibration': None})
        result[probe] = intervals
    return result
