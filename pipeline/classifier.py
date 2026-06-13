"""
pipeline/classifier.py
Calls the Claude API for a single transaction and returns a validated result dict.
"""

import json
import os
import time
from pathlib import Path

import anthropic

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
PROMPT_PATH    = Path(__file__).parent.parent / "prompts" / "system_prompt_v2.txt"
MODEL          = "claude-sonnet-4-6"
MAX_TOKENS     = 2000
MAX_RETRIES    = 3
RETRY_DELAY    = 2.0   # seconds between retries

REQUIRED_KEYS  = {
    "transaction_id", "customer_profile_used", "risk_level", "risk_score",
    "typologies_triggered", "jurisdiction_flags", "narrative",
    "recommended_action", "data_quality_flags", "disclaimer",
}

VALID_RISK_LEVELS  = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_ACTIONS      = {"MONITOR", "ESCALATE_FOR_REVIEW", "COMMUNICATE_TO_COAF"}
VALID_TYPOLOGIES   = {"STRUCTURING", "ATYPICAL_FREQUENCY", "HIGH_RISK_GEOGRAPHY", "PEP_INVOLVEMENT"}
VALID_STATUSES     = {"TRIGGERED", "NOT_TRIGGERED", "INSUFFICIENT_DATA"}


# ─────────────────────────────────────────────
# SYSTEM PROMPT LOADER
# ─────────────────────────────────────────────
_system_prompt_cache: str | None = None

def load_system_prompt() -> str:
    global _system_prompt_cache
    if _system_prompt_cache is None:
        if not PROMPT_PATH.exists():
            raise FileNotFoundError(
                f"System prompt not found at {PROMPT_PATH}.\n"
                "Copy system_prompt_v2.txt into the prompts/ folder."
            )
        _system_prompt_cache = PROMPT_PATH.read_text(encoding="utf-8").strip()
    return _system_prompt_cache


# ─────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────
class ClassificationError(Exception):
    """Raised when Claude returns an unparseable or invalid response."""

def validate_result(result: dict) -> dict:
    """
    Light schema validation. Raises ClassificationError if the response
    is missing required keys or has illegal enum values.
    Returns the result unchanged if valid.
    """
    missing = REQUIRED_KEYS - result.keys()
    if missing:
        raise ClassificationError(f"Missing keys in response: {missing}")

    if result["risk_level"] not in VALID_RISK_LEVELS:
        raise ClassificationError(f"Invalid risk_level: {result['risk_level']}")

    if result["recommended_action"] not in VALID_ACTIONS:
        raise ClassificationError(f"Invalid recommended_action: {result['recommended_action']}")

    if not isinstance(result["risk_score"], int) or not (0 <= result["risk_score"] <= 100):
        raise ClassificationError(f"Invalid risk_score: {result['risk_score']}")

    for t in result.get("typologies_triggered", []):
        if t.get("typology") not in VALID_TYPOLOGIES:
            raise ClassificationError(f"Unknown typology: {t.get('typology')}")
        if t.get("status") not in VALID_STATUSES:
            raise ClassificationError(f"Invalid typology status: {t.get('status')}")

    return result


# ─────────────────────────────────────────────
# RAW API CALL
# ─────────────────────────────────────────────
def _call_api(client: anthropic.Anthropic, system: str, user_content: str) -> str:
    """Single API call. Returns raw text content."""
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )

    if message.stop_reason == "max_tokens":
        raise ClassificationError("Response truncated — max_tokens reached.")

    return "".join(block.text for block in message.content if hasattr(block, "text"))


def _parse_json(raw: str) -> dict:
    """Strip markdown fences if present and parse JSON."""
    cleaned = raw.strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    # Extract first {...} block as a safety net
    start = cleaned.find("{")
    end   = cleaned.rfind("}") + 1
    if start == -1 or end == 0:
        raise ClassificationError(f"No JSON object found in response:\n{raw[:300]}")

    return json.loads(cleaned[start:end])


# ─────────────────────────────────────────────
# PUBLIC INTERFACE
# ─────────────────────────────────────────────
def classify_transaction(
    transaction: dict,
    client: anthropic.Anthropic | None = None,
    prompt_override: str | None = None,
) -> dict:
    """
    Classify a single transaction dict using the Claude API.

    Args:
        transaction:     The transaction dict (matching the v2 input schema).
        client:          Optional pre-built Anthropic client (re-use for batches).
        prompt_override: Optional system prompt string (defaults to prompts/v2.txt).

    Returns:
        Validated classification dict.

    Raises:
        ClassificationError: If the API returns an invalid or unparseable response
                             after all retries are exhausted.
    """
    if client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set. Add it to your .env file."
            )
        client = anthropic.Anthropic(api_key=api_key)

    system  = prompt_override or load_system_prompt()
    tx_json = json.dumps(transaction, indent=2, ensure_ascii=False)
    user_msg = (
        "Analyze the following transaction and respond with "
        "ONLY a valid JSON object, no other text:\n\n" + tx_json
    )

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw    = _call_api(client, system, user_msg)
            result = _parse_json(raw)
            result = validate_result(result)
            return result

        except (json.JSONDecodeError, ClassificationError) as e:
            last_error = e
            print(f"  [attempt {attempt}/{MAX_RETRIES}] Parse/validation error: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

        except anthropic.RateLimitError:
            wait = RETRY_DELAY * (2 ** attempt)
            print(f"  [attempt {attempt}/{MAX_RETRIES}] Rate limited — waiting {wait}s")
            time.sleep(wait)

        except anthropic.APIError as e:
            last_error = e
            print(f"  [attempt {attempt}/{MAX_RETRIES}] API error: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    raise ClassificationError(
        f"Failed to classify transaction {transaction.get('transaction_id')} "
        f"after {MAX_RETRIES} attempts. Last error: {last_error}"
    )


# ─────────────────────────────────────────────
# QUICK SMOKE TEST (single transaction)
# ─────────────────────────────────────────────
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    # Canonical scenario 2 — smurfing
    test_tx = {
        "transaction_id": "TXN-SMOKE-01",
        "transaction_timestamp": "2026-06-12T14:33:00-03:00",
        "transaction_type": "PIX",
        "direction": "OUTBOUND",
        "amount_brl": 9750.00,
        "purpose_description": None,
        "sender_type": "CPF",
        "sender_id_hash": "CPF-HASH-SMOKE",
        "sender_is_pep": False,
        "sender_jurisdiction": "BRA",
        "customer_profile": "PF_STANDARD",
        "receiver_type": "CNPJ",
        "receiver_id_hash": "CNPJ-HASH-SMOKE",
        "receiver_is_pep": False,
        "receiver_jurisdiction": "BRA",
        "transactions_last_24h_same_sender": 7,
        "transactions_last_72h_same_sender": 4,
        "total_amount_last_72h_same_sender_brl": 28900.00,
        "avg_monthly_amount_brl": 4500.00,
    }

    print(f"Classifying {test_tx['transaction_id']}...")
    result = classify_transaction(test_tx)
    print(json.dumps(result, indent=2, ensure_ascii=False))
