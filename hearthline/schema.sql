CREATE TABLE IF NOT EXISTS logbook (
    id TEXT PRIMARY KEY,
    evidence_hash TEXT NOT NULL,
    evidence TEXT NOT NULL,
    analysis_hash TEXT NOT NULL,
    analysis TEXT NOT NULL,
    received TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS review_event (
    run_id TEXT NOT NULL REFERENCES logbook(id),
    revision INTEGER NOT NULL,
    tray TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('accept', 'hold')),
    reviewer TEXT NOT NULL,
    note TEXT NOT NULL,
    PRIMARY KEY (run_id, revision)
);
CREATE TABLE IF NOT EXISTS dispatch (
    run_id TEXT NOT NULL REFERENCES logbook(id),
    batch_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('batch', 'whole')),
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    received TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, batch_id)
);
CREATE TABLE IF NOT EXISTS dispatch_tray (
    run_id TEXT NOT NULL REFERENCES logbook(id),
    tray TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    PRIMARY KEY (run_id, tray)
);
CREATE INDEX IF NOT EXISTS dispatch_tray_batch ON dispatch_tray(run_id, batch_id);
CREATE TABLE IF NOT EXISTS dispatch_precheck (
    run_id TEXT NOT NULL REFERENCES logbook(id),
    batch_id TEXT NOT NULL,
    precheck_hash TEXT NOT NULL,
    revision INTEGER NOT NULL,
    trays TEXT NOT NULL,
    content TEXT NOT NULL,
    updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, batch_id)
);
