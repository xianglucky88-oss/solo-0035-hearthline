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
    run_id TEXT PRIMARY KEY REFERENCES logbook(id),
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL
);
