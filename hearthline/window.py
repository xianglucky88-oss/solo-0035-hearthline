from bisect import bisect_right


class ProbeTimeline:
    def __init__(self, segments):
        self.segments = segments
        self.ends = [segment['to'] for segment in segments]

    def clip(self, start, end):
        cursor = start
        for index in range(bisect_right(self.ends, start), len(self.segments)):
            segment = self.segments[index]
            if segment['from'] >= end:
                break
            lower = max(start, segment['from'])
            upper = min(end, segment['to'])
            if lower > cursor:
                yield missing(cursor, lower)
            yield {**segment, 'from': lower, 'to': upper}
            cursor = upper
        if cursor < end:
            yield missing(cursor, end)


def missing(start, end):
    return {'from': start, 'to': end, 'reason': 'outside_samples',
            'sources': [], 'tenth': None, 'calibration': None}
