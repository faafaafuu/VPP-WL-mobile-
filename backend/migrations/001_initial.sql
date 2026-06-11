CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    product_id TEXT NOT NULL,
    original_transaction_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    tag TEXT NOT NULL UNIQUE,
    region TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'unknown',
    country_code TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    protocol TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL,
    weight INTEGER NOT NULL DEFAULT 100,
    health_score INTEGER NOT NULL DEFAULT 100,
    latency_ms INTEGER,
    success_rate REAL NOT NULL DEFAULT 1.0,
    last_check_at TEXT,
    health TEXT NOT NULL DEFAULT 'healthy',
    options_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_nodes_status_priority ON nodes(status, priority);
