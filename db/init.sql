CREATE TABLE IF NOT EXISTS sessions (
    session_id        TEXT PRIMARY KEY,
    project           TEXT NOT NULL,
    git_branch        TEXT,
    model             TEXT,
    started_at        TIMESTAMPTZ NOT NULL,
    ended_at          TIMESTAMPTZ,
    version           TEXT,
    is_subagent       BOOLEAN DEFAULT FALSE,
    parent_session_id TEXT REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS messages (
    message_uuid TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL REFERENCES sessions(session_id),
    timestamp    TIMESTAMPTZ NOT NULL,
    role         TEXT NOT NULL,
    prompt_type  TEXT NOT NULL,
    prompt_text  TEXT,
    tool_name    TEXT
);

CREATE TABLE IF NOT EXISTS token_usage (
    message_uuid          TEXT PRIMARY KEY REFERENCES messages(message_uuid),
    model                 TEXT,
    input_tokens          INTEGER DEFAULT 0,
    output_tokens         INTEGER DEFAULT 0,
    cache_read_tokens     INTEGER DEFAULT 0,
    cache_creation_tokens INTEGER DEFAULT 0,
    service_tier          TEXT
);

CREATE TABLE IF NOT EXISTS usage_snapshots (
    id              SERIAL PRIMARY KEY,
    "timestamp"     TIMESTAMPTZ NOT NULL,
    window_name     TEXT NOT NULL,
    utilization_pct REAL NOT NULL,
    resets_at       TIMESTAMPTZ,
    plan            TEXT
);

CREATE TABLE IF NOT EXISTS scraper_state (
    file_path     TEXT PRIMARY KEY,
    last_offset   BIGINT DEFAULT 0,
    last_modified TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_token_usage_model ON token_usage(model);
CREATE INDEX IF NOT EXISTS idx_usage_snapshots_timestamp ON usage_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
