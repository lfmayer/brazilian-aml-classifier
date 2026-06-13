-- schema.sql
-- Brazilian AML Risk Classifier — SQLite Schema v1.0

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────
-- RAW TRANSACTIONS (input)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id                              INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id                  TEXT    NOT NULL UNIQUE,
    transaction_timestamp           TEXT    NOT NULL,  -- ISO 8601
    transaction_type                TEXT    NOT NULL,  -- PIX|TED|DOC|CASH_DEPOSIT|CASH_WITHDRAWAL|WIRE_TRANSFER
    direction                       TEXT    NOT NULL,  -- INBOUND|OUTBOUND
    amount_brl                      REAL    NOT NULL,
    purpose_description             TEXT,              -- nullable
    sender_type                     TEXT    NOT NULL,  -- CPF|CNPJ
    sender_id_hash                  TEXT    NOT NULL,
    sender_is_pep                   INTEGER NOT NULL DEFAULT 0,  -- 0|1
    sender_jurisdiction             TEXT    NOT NULL DEFAULT 'BRA',
    customer_profile                TEXT    NOT NULL,  -- PF_STANDARD|PF_HIGH_INCOME|PJ_SME|PJ_LARGE|UNKNOWN
    receiver_type                   TEXT    NOT NULL,
    receiver_id_hash                TEXT    NOT NULL,
    receiver_is_pep                 INTEGER NOT NULL DEFAULT 0,
    receiver_jurisdiction           TEXT    NOT NULL DEFAULT 'BRA',
    transactions_last_24h           INTEGER NOT NULL DEFAULT 0,
    transactions_last_72h           INTEGER NOT NULL DEFAULT 0,
    total_amount_last_72h_brl       REAL    NOT NULL DEFAULT 0.0,
    avg_monthly_amount_brl          REAL,              -- nullable
    created_at                      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────
-- CLASSIFICATION RESULTS (output from Claude)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS classifications (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id          TEXT    NOT NULL REFERENCES transactions(transaction_id),
    customer_profile_used   TEXT    NOT NULL,
    risk_level              TEXT    NOT NULL,   -- LOW|MEDIUM|HIGH|CRITICAL
    risk_score              INTEGER NOT NULL,   -- 0–100
    recommended_action      TEXT    NOT NULL,   -- MONITOR|ESCALATE_FOR_REVIEW|COMMUNICATE_TO_COAF
    narrative               TEXT    NOT NULL,
    raw_response_json       TEXT    NOT NULL,   -- full Claude JSON stored as text
    prompt_version          TEXT    NOT NULL DEFAULT 'v2',
    classified_at           TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────
-- TYPOLOGY RESULTS (one row per typology per tx)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS typology_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    classification_id   INTEGER NOT NULL REFERENCES classifications(id),
    transaction_id      TEXT    NOT NULL,
    typology            TEXT    NOT NULL,   -- STRUCTURING|ATYPICAL_FREQUENCY|HIGH_RISK_GEOGRAPHY|PEP_INVOLVEMENT
    status              TEXT    NOT NULL,   -- TRIGGERED|NOT_TRIGGERED|INSUFFICIENT_DATA
    signals_identified  TEXT    NOT NULL    -- JSON array stored as text
);

-- ─────────────────────────────────────────────
-- JURISDICTION FLAGS (one row per jurisdiction per tx)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS jurisdiction_flags (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    classification_id   INTEGER NOT NULL REFERENCES classifications(id),
    transaction_id      TEXT    NOT NULL,
    jurisdiction_code   TEXT    NOT NULL,
    list_membership     TEXT    NOT NULL,   -- JSON array: ["FATF_BLACKLIST", ...]
    risk_contribution   TEXT    NOT NULL    -- HIGH|MEDIUM|LOW|NONE
);

-- ─────────────────────────────────────────────
-- DATA QUALITY FLAGS (one row per flag per tx)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_quality_flags (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    classification_id   INTEGER NOT NULL REFERENCES classifications(id),
    transaction_id      TEXT    NOT NULL,
    flag_description    TEXT    NOT NULL
);

-- ─────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_tx_sender      ON transactions(sender_id_hash);
CREATE INDEX IF NOT EXISTS idx_tx_timestamp   ON transactions(transaction_timestamp);
CREATE INDEX IF NOT EXISTS idx_cls_risk       ON classifications(risk_level);
CREATE INDEX IF NOT EXISTS idx_cls_tx         ON classifications(transaction_id);
CREATE INDEX IF NOT EXISTS idx_typology_tx    ON typology_results(transaction_id);
