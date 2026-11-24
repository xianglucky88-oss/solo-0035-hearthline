from .analysis import ENGINE, analyze
from .archive import get_run, read_document
from .codec import digest
from .errors import Problem
from .handoff import current_dispatch, prepare
from .intake import normalize


def verify(db, run_id):
    row = get_run(db, run_id)
    source = normalize(read_document(row, 'evidence'))
    report = read_document(row, 'analysis')
    if report['engine'] != ENGINE:
        raise Problem('当前计算引擎与存档版本不一致', 409)
    actual = analyze(source)
    source_match = digest(source) == row['evidence_hash']
    report_match = digest(actual) == row['analysis_hash'] == digest(report)
    dispatch = current_dispatch(db, run_id)
    match = None
    if dispatch:
        match = digest(prepare(db, run_id)) == dispatch['dispatch_hash']
    return {'run': run_id, 'evidence_match': source_match, 'analysis_match': report_match, 'dispatch_match': match,
            'ok': source_match and report_match and match is not False}
