from .archive import get_run, read_document
from .handoff import dispatched_trays, list_dispatches, whole_dispatch
from .review_log import review_state


def load(db, run_id):
    row = get_run(db, run_id)
    report = read_document(row, 'analysis')
    # Detailed evidence is retrieved on demand for one tray.
    for tray in report['trays']:
        for stage in tray['stages']:
            stage['timeline'] = [{'from': part['from'], 'to': part['to'], 'status': part['status']}
                                 for part in stage.pop('slices')]
    whole = whole_dispatch(db, run_id)
    taken = dispatched_trays(db, run_id)
    return {'report': report, 'evidence_hash': row['evidence_hash'], 'reviews': review_state(db, run_id),
            'dispatch_hash': (whole or {}).get('dispatch_hash'),
            'whole_frozen': whole is not None,
            'dispatched': taken,
            'dispatches': list_dispatches(db, run_id)}
