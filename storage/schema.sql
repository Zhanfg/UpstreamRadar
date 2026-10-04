PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS repositories (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    full_name TEXT NOT NULL,
    ecosystem TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    UNIQUE(source, full_name)
);

CREATE TABLE IF NOT EXISTS radar_events (
    id INTEGER PRIMARY KEY,
    repository_id INTEGER NOT NULL,
    observed_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    semantic_impact REAL NOT NULL CHECK (semantic_impact >= 0),
    fingerprint TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(repository_id) REFERENCES repositories(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_radar_events_repository_time
ON radar_events(repository_id, observed_at DESC);

CREATE INDEX IF NOT EXISTS idx_radar_events_impact
ON radar_events(semantic_impact DESC);
