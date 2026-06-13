"""
db/database.py
SQLite connection and helper functions for the AML classifier.
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "outputs" / "results.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create all tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text())
    print(f"Database initialized at {DB_PATH}")


def insert_transaction(tx: dict) -> None:
    sql = """
        INSERT OR IGNORE INTO transactions (
            transaction_id, transaction_timestamp, transaction_type, direction,
            amount_brl, purpose_description, sender_type, sender_id_hash,
            sender_is_pep, sender_jurisdiction, customer_profile,
            receiver_type, receiver_id_hash, receiver_is_pep, receiver_jurisdiction,
            transactions_last_24h, transactions_last_72h,
            total_amount_last_72h_brl, avg_monthly_amount_brl
        ) VALUES (
            :transaction_id, :transaction_timestamp, :transaction_type, :direction,
            :amount_brl, :purpose_description, :sender_type, :sender_id_hash,
            :sender_is_pep, :sender_jurisdiction, :customer_profile,
            :receiver_type, :receiver_id_hash, :receiver_is_pep, :receiver_jurisdiction,
            :transactions_last_24h_same_sender, :transactions_last_72h_same_sender,
            :total_amount_last_72h_same_sender_brl, :avg_monthly_amount_brl
        )
    """
    with get_connection() as conn:
        conn.execute(sql, tx)


def insert_classification(tx_id: str, result: dict, prompt_version: str = "v2") -> int:
    """Insert a Claude classification result. Returns the new classification id."""
    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO classifications (
                transaction_id, customer_profile_used, risk_level, risk_score,
                recommended_action, narrative, raw_response_json, prompt_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tx_id,
            result["customer_profile_used"],
            result["risk_level"],
            result["risk_score"],
            result["recommended_action"],
            result["narrative"],
            json.dumps(result),
            prompt_version,
        ))
        cls_id = cur.lastrowid

        for t in result.get("typologies_triggered", []):
            conn.execute("""
                INSERT INTO typology_results (classification_id, transaction_id, typology, status, signals_identified)
                VALUES (?, ?, ?, ?, ?)
            """, (cls_id, tx_id, t["typology"], t["status"], json.dumps(t["signals_identified"])))

        for j in result.get("jurisdiction_flags", []):
            conn.execute("""
                INSERT INTO jurisdiction_flags (classification_id, transaction_id, jurisdiction_code, list_membership, risk_contribution)
                VALUES (?, ?, ?, ?, ?)
            """, (cls_id, tx_id, j["jurisdiction_code"], json.dumps(j["list_membership"]), j["risk_contribution"]))

        for flag in result.get("data_quality_flags", []):
            conn.execute("""
                INSERT INTO data_quality_flags (classification_id, transaction_id, flag_description)
                VALUES (?, ?, ?)
            """, (cls_id, tx_id, flag))

        return cls_id


def fetch_unclassified(limit: int = 50) -> list[dict]:
    """Return transactions that have no classification yet."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT t.* FROM transactions t
            LEFT JOIN classifications c ON t.transaction_id = c.transaction_id
            WHERE c.id IS NULL
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def fetch_classifications_df() -> list[dict]:
    """Return all classified transactions joined with classification results."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                t.transaction_id, t.transaction_timestamp, t.transaction_type,
                t.direction, t.amount_brl, t.customer_profile,
                t.sender_jurisdiction, t.receiver_jurisdiction,
                t.sender_is_pep, t.receiver_is_pep,
                c.risk_level, c.risk_score, c.recommended_action,
                c.narrative, c.classified_at, c.id as classification_id
            FROM transactions t
            INNER JOIN classifications c ON t.transaction_id = c.transaction_id
            ORDER BY c.risk_score DESC, c.classified_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def fetch_typology_counts() -> list[dict]:
    """Count TRIGGERED typologies grouped by type."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT typology, COUNT(*) as n
            FROM typology_results
            WHERE status = 'TRIGGERED'
            GROUP BY typology
            ORDER BY n DESC
        """).fetchall()
        return [dict(r) for r in rows]


def fetch_jurisdiction_hits() -> list[dict]:
    """Top jurisdictions flagged, excluding BRA."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT jurisdiction_code, risk_contribution, COUNT(*) as n
            FROM jurisdiction_flags
            WHERE risk_contribution != 'NONE' AND jurisdiction_code != 'BRA'
            GROUP BY jurisdiction_code, risk_contribution
            ORDER BY n DESC
            LIMIT 20
        """).fetchall()
        return [dict(r) for r in rows]


def fetch_classification_detail(tx_id: str) -> dict | None:
    """Full detail for a single transaction + classification."""
    with get_connection() as conn:
        tx = conn.execute(
            "SELECT * FROM transactions WHERE transaction_id = ?", (tx_id,)
        ).fetchone()
        cls = conn.execute(
            "SELECT * FROM classifications WHERE transaction_id = ? ORDER BY id DESC LIMIT 1",
            (tx_id,)
        ).fetchone()
        if not tx or not cls:
            return None

        typologies = conn.execute(
            "SELECT * FROM typology_results WHERE classification_id = ?", (cls["id"],)
        ).fetchall()
        jurisdictions = conn.execute(
            "SELECT * FROM jurisdiction_flags WHERE classification_id = ?", (cls["id"],)
        ).fetchall()
        dq_flags = conn.execute(
            "SELECT flag_description FROM data_quality_flags WHERE classification_id = ?",
            (cls["id"],)
        ).fetchall()

        return {
            "transaction":  dict(tx),
            "classification": dict(cls),
            "typologies":   [dict(r) for r in typologies],
            "jurisdictions": [dict(r) for r in jurisdictions],
            "dq_flags":     [r["flag_description"] for r in dq_flags],
        }


def fetch_summary() -> dict:
    """Quick stats for the Streamlit dashboard."""
    with get_connection() as conn:
        total   = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        done    = conn.execute("SELECT COUNT(*) FROM classifications").fetchone()[0]
        by_risk = conn.execute("""
            SELECT risk_level, COUNT(*) as n FROM classifications GROUP BY risk_level
        """).fetchall()
        return {
            "total_transactions": total,
            "classified": done,
            "pending": total - done,
            "by_risk_level": {r["risk_level"]: r["n"] for r in by_risk},
        }
