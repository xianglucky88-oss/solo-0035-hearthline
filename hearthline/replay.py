from .analysis import ENGINE, analyze
from .archive import get_run, read_document
from .codec import digest
from .errors import Problem
from .handoff import get_dispatch, list_dispatches
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
    # 冻结件固化的是当时的原始炉次证据摘要、分析摘要和本批采用的签认。
    # 之后的补签或其他批次交接不改变旧件，因此只核对其引用的证据/分析是否仍是归档原件。
    checks = []
    for item in list_dispatches(db, run_id):
        frozen = get_dispatch(db, run_id, item['batch_id'])
        anchor_match = (frozen['evidence_hash'] == row['evidence_hash']
                        and frozen['analysis_hash'] == row['analysis_hash']
                        and digest({k: frozen[k] for k in frozen if k != 'dispatch_hash'})
                        == item['content_hash'])
        checks.append({'batch': item['batch_id'], 'mode': frozen['mode'],
                       'dispatch_hash': item['content_hash'], 'match': anchor_match})
    all_match = all(item['match'] for item in checks) if checks else None
    return {'run': run_id, 'evidence_match': source_match, 'analysis_match': report_match,
            'dispatch_match': all_match, 'dispatch_checks': checks,
            'ok': source_match and report_match and all_match is not False}
