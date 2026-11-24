from .analysis import trace_piece as compute_piece_trace
from .errors import Problem


def _transfer_map(report):
    return {item['id']: item for item in report.get('transfers', [])}


def _evidence_from_stages(stages, source):
    readings = {ref for stage in stages for part in stage.get('slices', [])
                for ref in part.get('sources', [])}
    calibrations = {part.get('calibration') for stage in stages
                    for part in stage.get('slices', []) if part.get('calibration')}
    return (
        [row for row in source['readings'] if row['id'] in readings],
        [row for row in source['calibrations'] if row['id'] in calibrations],
    )


def trace_piece(report, source, piece_id):
    summary = next((item for item in report.get('workpieces', []) if item['id'] == piece_id), None)
    if summary is None:
        return None
    piece = compute_piece_trace(source, piece_id) or summary
    tray_ids = {segment['tray'] for segment in piece.get('tenures', [])}
    transfer_ids = set(piece.get('transfers', []))
    transfers_map = _transfer_map(report)
    events = [event for event in source['events'] if event['tray'] in tray_ids]
    for issue in piece.get('issues', []):
        # Issue source refs are sample/gate identifiers; include matching gates.
        ids = set(issue.get('sources', []))
        events.extend(event for event in source['events'] if event['id'] in ids)
    readings, calibrations = _evidence_from_stages(piece.get('stages', []), source)
    transfers = [transfers_map[tid] for tid in piece.get('transfers', []) if tid in transfers_map]
    result = {
        'piece': piece,
        'workpiece': piece,
        'events': _dedupe(events, 'id'),
        'readings': readings,
        'calibrations': calibrations,
        'transfers': transfers,
        'handovers': transfers,
        'tenures': piece.get('tenures', []),
    }
    return result


def trace_tray(report, source, tray_id):
    tray = next((tray for tray in report['trays'] if tray['id'] == tray_id), None)
    if tray is None:
        piece_result = trace_piece(report, source, tray_id)
        if piece_result is not None:
            return piece_result
        raise Problem('没有找到该料盘或工件', 404)
    events = {event['id'] for event in source['events'] if event['tray'] == tray_id}
    for issue in tray['issues']:
        for collision in issue.get('conflicts', []):
            events.update(collision['sources'])
    segments = [part for stage in tray['stages'] for part in stage['slices']]
    readings = {ref for part in segments for ref in part['sources']}
    calibrations = {part['calibration'] for part in segments if part['calibration']}

    piece_ids = set(tray.get('piece_ids', tray.get('workpiece_ids', [])))
    transfer_ids = set()
    transfer_map = _transfer_map(report)
    for transfer in report.get('transfers', []):
        if tray_id in transfer.get('involved_trays', []):
            transfer_ids.add(transfer['id'])
        if any(move.get('piece') in piece_ids for move in transfer.get('moves', [])):
            transfer_ids.add(transfer['id'])
    transfers = [transfer_map[tid] for tid in sorted(transfer_ids) if tid in transfer_map]
    piece_traces = [trace_piece(report, source, pid) for pid in sorted(piece_ids)]
    piece_traces = [item for item in piece_traces if item is not None]
    return {
        'tray': tray,
        'events': [event for event in source['events'] if event['id'] in events],
        'readings': [row for row in source['readings'] if row['id'] in readings],
        'calibrations': [row for row in source['calibrations'] if row['id'] in calibrations],
        'pieces': tray.get('pieces', tray.get('workpieces', [])),
        'workpieces': tray.get('workpieces', tray.get('pieces', [])),
        'piece_traces': piece_traces,
        'workpiece_traces': piece_traces,
        'transfers': transfers,
        'handovers': transfers,
        'missing_evidence_pieces': tray.get('missing_evidence_pieces', []),
    }


def _dedupe(rows, key):
    seen = set()
    result = []
    for row in rows:
        if row[key] not in seen:
            seen.add(row[key])
            result.append(row)
    return result
