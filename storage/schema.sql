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


CREATE TABLE IF NOT EXISTS harmony_scores (
    event_id INTEGER PRIMARY KEY,
    change_probability REAL NOT NULL CHECK (change_probability BETWEEN 0 AND 1),
    graph_influence REAL NOT NULL CHECK (graph_influence BETWEEN 0 AND 1),
    bayesian_surprise REAL NOT NULL CHECK (bayesian_surprise BETWEEN 0 AND 1),
    structural_novelty REAL NOT NULL CHECK (structural_novelty BETWEEN 0 AND 1),
    tail_risk REAL NOT NULL CHECK (tail_risk BETWEEN 0 AND 1),
    risk_adjusted_utility REAL NOT NULL CHECK (risk_adjusted_utility >= 0),
    base_utility REAL NOT NULL CHECK (base_utility >= 0),
    FOREIGN KEY(event_id) REFERENCES radar_events(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_harmony_scores_utility
ON harmony_scores(base_utility DESC, tail_risk ASC);

CREATE VIEW IF NOT EXISTS v_priority_events AS
SELECT
    e.id,
    r.source,
    r.full_name,
    e.observed_at,
    e.event_type,
    e.semantic_impact,
    s.bayesian_surprise,
    s.structural_novelty,
    s.tail_risk,
    s.risk_adjusted_utility,
    s.base_utility
FROM radar_events e
JOIN repositories r ON r.id = e.repository_id
JOIN harmony_scores s ON s.event_id = e.id
ORDER BY s.base_utility DESC, s.tail_risk ASC, e.observed_at DESC;
