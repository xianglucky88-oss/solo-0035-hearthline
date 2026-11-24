from .errors import Problem


def trace_tray(report, source, tray_id):
    tray = next((tray for tray in report['trays'] if tray['id'] == tray_id), None)
    if tray is None:
        raise Problem('没有找到该料盘', 404)
    events = {event['id'] for event in source['events'] if event['tray'] == tray_id}
    for issue in tray['issues']:
        for collision in issue.get('conflicts', []):
            events.update(collision['sources'])
    segments = [part for stage in tray['stages'] for part in stage['slices']]
    readings = {ref for part in segments for ref in part['sources']}
    calibrations = {part['calibration'] for part in segments if part['calibration']}
    return {'tray': tray, 'events': [event for event in source['events'] if event['id'] in events],
            'readings': [row for row in source['readings'] if row['id'] in readings],
            'calibrations': [row for row in source['calibrations'] if row['id'] in calibrations]}
