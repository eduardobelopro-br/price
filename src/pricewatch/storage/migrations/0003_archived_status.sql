CREATE TABLE products_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    variant_key TEXT,
    title TEXT,
    status TEXT NOT NULL CHECK (status IN ('active', 'paused', 'unsupported', 'error', 'archived')),
    check_interval_seconds INTEGER NOT NULL,
    next_check_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    consecutive_failures INTEGER NOT NULL DEFAULT 0
);

INSERT INTO products_new (
    id, url, variant_key, title, status, check_interval_seconds,
    next_check_at, created_at, updated_at, consecutive_failures
)
SELECT
    id, url, variant_key, title, status, check_interval_seconds,
    next_check_at, created_at, updated_at, consecutive_failures
FROM products;

DROP TABLE products;
ALTER TABLE products_new RENAME TO products;

CREATE INDEX idx_products_next_check_at ON products (next_check_at);
