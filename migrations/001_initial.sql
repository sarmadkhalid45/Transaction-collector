-- Applied automatically by app.initialize_db() on startup.
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','user')),
    active INTEGER NOT NULL DEFAULT 1,
    consent_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    transaction_date TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    category TEXT NOT NULL,
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    description TEXT NOT NULL,
    reference_number TEXT NOT NULL DEFAULT '',
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending',
    sync_error TEXT NOT NULL DEFAULT '',
    deleted_at TEXT,
    idempotency_key TEXT
);
CREATE INDEX IF NOT EXISTS idx_tx_user_date ON transactions(user_id, transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_tx_sync ON transactions(sync_status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_user_idempotency ON transactions(user_id,idempotency_key) WHERE idempotency_key IS NOT NULL AND deleted_at IS NULL;
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
