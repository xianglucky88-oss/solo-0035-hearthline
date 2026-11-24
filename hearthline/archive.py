from .analysis import analyze
from .codec import canonical, decode, digest
from .errors import Problem
from .intake import normalize


def preview(value):
    source = normalize(value)
    return source, analyze(source)


def receive(store, value):
    source, report = preview(value)
    source_hash = digest(source)
    with store.connection(write=True) as db:
        current = db.execute('SELECT evidence_hash FROM logbook WHERE id=?', (source['id'],)).fetchone()
        if current is not None:
            if current['evidence_hash'] != source_hash:
                raise Problem('同一炉次编号已归档其他证据', 409)
            return {'id': source['id'], 'evidence_hash': source_hash, 'created': False}
        db.execute('INSERT INTO logbook(id, evidence_hash, evidence, analysis_hash, analysis) VALUES(?,?,?,?,?)',
                   (source['id'], source_hash, canonical(source), digest(report), canonical(report)))
    return {'id': source['id'], 'evidence_hash': source_hash, 'created': True}


def list_runs(db, offset):
    rows = db.execute('SELECT id, evidence_hash, received FROM logbook ORDER BY received DESC, id LIMIT 30 OFFSET ?',
                      (offset,))
    return [dict(row) for row in rows]


def get_run(db, run_id):
    row = db.execute('SELECT * FROM logbook WHERE id=?', (run_id,)).fetchone()
    if row is None:
        raise Problem('没有找到该炉次', 404)
    return row


def read_document(row, name):
    return decode(row[name].encode('utf-8'))
