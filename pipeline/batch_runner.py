"""
pipeline/batch_runner.py
Reads unclassified transactions from SQLite, classifies each via Claude,
and writes results back to the database.

Usage:
    python -m pipeline.batch_runner              # classify all pending
    python -m pipeline.batch_runner --limit 10   # classify up to 10
    python -m pipeline.batch_runner --dry-run    # print without saving
"""

import argparse
import json
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# Allow running as script from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import (
    init_db,
    insert_transaction,
    insert_classification,
    fetch_unclassified,
    fetch_summary,
)
from pipeline.classifier import classify_transaction, ClassificationError, load_system_prompt

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
REQUEST_DELAY = 0.5   # seconds between API calls (rate limit safety)
PROMPT_VERSION = "v2"


# ─────────────────────────────────────────────
# SEED: load synthetic data into DB if empty
# ─────────────────────────────────────────────
def seed_from_json(json_path: Path) -> int:
    """Load transactions from JSON into the DB. Returns count inserted."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    inserted = 0
    for tx in data:
        try:
            insert_transaction(tx)
            inserted += 1
        except Exception as e:
            print(f"  Skipped {tx.get('transaction_id')}: {e}")
    return inserted


# ─────────────────────────────────────────────
# PROGRESS DISPLAY
# ─────────────────────────────────────────────
RISK_COLORS = {
    "LOW":      "\033[92m",   # green
    "MEDIUM":   "\033[93m",   # yellow
    "HIGH":     "\033[91m",   # red
    "CRITICAL": "\033[95m",   # magenta
}
RESET = "\033[0m"

def print_result(tx_id: str, result: dict, elapsed: float) -> None:
    level  = result["risk_level"]
    score  = result["risk_score"]
    action = result["recommended_action"]
    color  = RISK_COLORS.get(level, "")
    triggered = [
        t["typology"] for t in result["typologies_triggered"]
        if t["status"] == "TRIGGERED"
    ]
    flags = ", ".join(triggered) if triggered else "—"
    print(
        f"  {tx_id:<18} {color}{level:<10}{RESET} "
        f"score={score:>3}  action={action:<25} "
        f"flags=[{flags}]  ({elapsed:.1f}s)"
    )


# ─────────────────────────────────────────────
# MAIN RUNNER
# ─────────────────────────────────────────────
def run_batch(limit: int = 100, dry_run: bool = False) -> None:
    init_db()

    # Seed DB from synthetic JSON if empty
    json_path = Path(__file__).parent.parent / "data" / "synthetic_transactions.json"
    if json_path.exists():
        n = seed_from_json(json_path)
        if n:
            print(f"Seeded {n} transactions into the database.")

    pending = fetch_unclassified(limit=limit)
    if not pending:
        print("No unclassified transactions found.")
        summary = fetch_summary()
        print(f"Database summary: {summary}")
        return

    print(f"\nClassifying {len(pending)} transactions "
          f"({'DRY RUN — not saving' if dry_run else f'saving to DB'})...\n")

    system_prompt = load_system_prompt()
    client = anthropic.Anthropic()

    stats = {"ok": 0, "error": 0, "by_risk": {}}
    errors = []

    for i, tx in enumerate(pending, start=1):
        tx_id = tx["transaction_id"]
        print(f"[{i:>3}/{len(pending)}] ", end="", flush=True)

        t0 = time.time()
        try:
            result  = classify_transaction(tx, client=client, prompt_override=system_prompt)
            elapsed = time.time() - t0

            print_result(tx_id, result, elapsed)

            if not dry_run:
                insert_classification(tx_id, result, prompt_version=PROMPT_VERSION)

            stats["ok"] += 1
            level = result["risk_level"]
            stats["by_risk"][level] = stats["by_risk"].get(level, 0) + 1

        except ClassificationError as e:
            elapsed = time.time() - t0
            print(f"  {tx_id:<18} \033[91mERROR\033[0m  {e}  ({elapsed:.1f}s)")
            stats["error"] += 1
            errors.append({"transaction_id": tx_id, "error": str(e)})

        time.sleep(REQUEST_DELAY)

    # ── Summary ──────────────────────────────
    print("\n" + "─" * 70)
    print(f"Done.  Classified: {stats['ok']}  Errors: {stats['error']}")
    print(f"Risk distribution: {stats['by_risk']}")

    if errors:
        err_path = Path(__file__).parent.parent / "outputs" / "errors.json"
        err_path.write_text(json.dumps(errors, indent=2))
        print(f"Errors logged to {err_path}")

    if not dry_run:
        db_summary = fetch_summary()
        print(f"Database totals: {db_summary}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AML Batch Classifier")
    parser.add_argument("--limit",   type=int,  default=100,  help="Max transactions to classify")
    parser.add_argument("--dry-run", action="store_true",     help="Classify but do not save to DB")
    args = parser.parse_args()

    run_batch(limit=args.limit, dry_run=args.dry_run)
