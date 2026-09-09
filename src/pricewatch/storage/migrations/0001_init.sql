CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    variant_key TEXT,
    title TEXT,
    status TEXT NOT NULL CHECK (status IN ('active', 'paused', 'unsupported', 'error')),
    check_interval_seconds INTEGER NOT NULL,
    next_check_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX idx_products_next_check_at ON products (next_check_at);

CREATE TABLE snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products (id),
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    source TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK (source_kind IN ('real', 'demo')),
    price_scope TEXT NOT NULL CHECK (price_scope IN ('item', 'item_shipping', 'landed')),
    title TEXT,
    variant_key TEXT,
    seller TEXT,
    availability TEXT,
    confidence TEXT NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
    observed_at TEXT NOT NULL
);

CREATE INDEX idx_snapshots_product_observed ON snapshots (product_id, observed_at);

CREATE TABLE collection_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products (id),
    collector TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('success', 'error')),
    error_code TEXT,
    error_message TEXT,
    observed_at TEXT NOT NULL
);

CREATE INDEX idx_collection_attempts_product ON collection_attempts (product_id, observed_at);

CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products (id),
    kind TEXT NOT NULL CHECK (kind IN ('target_price', 'absolute_drop', 'percentage_drop', 'new_low')),
    threshold TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_rules_product ON rules (product_id);

CREATE TABLE alert_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products (id),
    rule_id INTEGER NOT NULL REFERENCES rules (id),
    idempotency_key TEXT NOT NULL UNIQUE,
    reference_price TEXT NOT NULL,
    current_price TEXT NOT NULL,
    currency TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_event_id INTEGER NOT NULL REFERENCES alert_events (id),
    channel TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    last_error TEXT
);

CREATE INDEX idx_outbox_status_next_attempt ON outbox (status, next_attempt_at);
