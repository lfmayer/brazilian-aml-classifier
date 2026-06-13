"""
tests/test_scenarios.py
Validates that the classifier returns the expected risk classification
for the three canonical scenarios defined in the HTML tester (aml_tester.html).

These tests call the real Claude API — they are integration tests, not unit tests.
Each test costs ~1 API call (~$0.001).

Run:
    python -m pytest tests/test_scenarios.py -v
    python -m pytest tests/test_scenarios.py -v -k "test_scenario_1"  # single test
"""

import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
from pipeline.classifier import classify_transaction, load_system_prompt

# ─────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Single Anthropic client reused across all tests in this module."""
    return anthropic.Anthropic()

@pytest.fixture(scope="module")
def system_prompt():
    return load_system_prompt()


# ─────────────────────────────────────────────
# CANONICAL SCENARIOS (from aml_tester.html)
# ─────────────────────────────────────────────

SCENARIO_1 = {
    "transaction_id": "TXN-00001",
    "transaction_timestamp": "2026-06-12T09:15:00-03:00",
    "transaction_type": "PIX",
    "direction": "OUTBOUND",
    "amount_brl": 1500.00,
    "purpose_description": "Pagamento de aluguel mensal",
    "sender_type": "CPF",
    "sender_id_hash": "CPF-HASH-A1B2C3",
    "sender_is_pep": False,
    "sender_jurisdiction": "BRA",
    "customer_profile": "PF_STANDARD",
    "receiver_type": "CPF",
    "receiver_id_hash": "CPF-HASH-D4E5F6",
    "receiver_is_pep": False,
    "receiver_jurisdiction": "BRA",
    "transactions_last_24h_same_sender": 1,
    "transactions_last_72h_same_sender": 2,
    "total_amount_last_72h_same_sender_brl": 2800.00,
    "avg_monthly_amount_brl": 3200.00,
}

SCENARIO_2 = {
    "transaction_id": "TXN-00002",
    "transaction_timestamp": "2026-06-12T14:33:00-03:00",
    "transaction_type": "PIX",
    "direction": "OUTBOUND",
    "amount_brl": 9750.00,
    "purpose_description": None,
    "sender_type": "CPF",
    "sender_id_hash": "CPF-HASH-G7H8I9",
    "sender_is_pep": False,
    "sender_jurisdiction": "BRA",
    "customer_profile": "PF_STANDARD",
    "receiver_type": "CNPJ",
    "receiver_id_hash": "CNPJ-HASH-J1K2L3",
    "receiver_is_pep": False,
    "receiver_jurisdiction": "BRA",
    "transactions_last_24h_same_sender": 7,
    "transactions_last_72h_same_sender": 4,
    "total_amount_last_72h_same_sender_brl": 28900.00,
    "avg_monthly_amount_brl": 4500.00,
}

SCENARIO_3 = {
    "transaction_id": "TXN-00003",
    "transaction_timestamp": "2026-06-12T17:05:00-03:00",
    "transaction_type": "WIRE_TRANSFER",
    "direction": "OUTBOUND",
    "amount_brl": 87500.00,
    "purpose_description": None,
    "sender_type": "CPF",
    "sender_id_hash": "CPF-HASH-M4N5O6",
    "sender_is_pep": True,
    "sender_jurisdiction": "BRA",
    "customer_profile": "PF_HIGH_INCOME",
    "receiver_type": "CNPJ",
    "receiver_id_hash": "CNPJ-HASH-P7Q8R9",
    "receiver_is_pep": False,
    "receiver_jurisdiction": "CYM",   # Cayman Islands — RFB tax haven
    "transactions_last_24h_same_sender": 3,
    "transactions_last_72h_same_sender": 5,
    "total_amount_last_72h_same_sender_brl": 142000.00,
    "avg_monthly_amount_brl": 25000.00,
}


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def triggered_typologies(result: dict) -> set[str]:
    return {
        t["typology"]
        for t in result["typologies_triggered"]
        if t["status"] == "TRIGGERED"
    }

def jurisdiction_codes(result: dict) -> set[str]:
    return {j["jurisdiction_code"] for j in result.get("jurisdiction_flags", [])}


# ─────────────────────────────────────────────
# SCENARIO 1 — Baixo Risco (Low Risk)
# PIX R$1.500, domestic, purpose documented, normal frequency
# Expected: LOW, no typologies triggered, MONITOR
# ─────────────────────────────────────────────

class TestScenario1LowRisk:

    @pytest.fixture(scope="class")
    def result(self, client, system_prompt):
        return classify_transaction(SCENARIO_1, client=client, prompt_override=system_prompt)

    def test_schema_complete(self, result):
        """Response contains all required fields."""
        required = {
            "transaction_id", "customer_profile_used", "risk_level", "risk_score",
            "typologies_triggered", "jurisdiction_flags", "narrative",
            "recommended_action", "data_quality_flags", "disclaimer",
        }
        assert required.issubset(result.keys()), f"Missing keys: {required - result.keys()}"

    def test_risk_level_is_low(self, result):
        assert result["risk_level"] == "LOW", (
            f"Expected LOW, got {result['risk_level']} (score={result['risk_score']})"
        )

    def test_risk_score_range(self, result):
        assert 0 <= result["risk_score"] <= 24, (
            f"LOW risk score should be 0–24, got {result['risk_score']}"
        )

    def test_no_typologies_triggered(self, result):
        triggered = triggered_typologies(result)
        assert not triggered, f"Expected no typologies triggered, got: {triggered}"

    def test_action_is_monitor(self, result):
        assert result["recommended_action"] == "MONITOR", (
            f"Expected MONITOR, got {result['recommended_action']}"
        )

    def test_transaction_id_preserved(self, result):
        assert result["transaction_id"] == "TXN-00001"

    def test_correct_profile_used(self, result):
        assert result["customer_profile_used"] == "PF_STANDARD"

    def test_narrative_present(self, result):
        assert len(result["narrative"]) >= 50, "Narrative too short"

    def test_disclaimer_present(self, result):
        assert "synthetic" in result["disclaimer"].lower() or "portfolio" in result["disclaimer"].lower()


# ─────────────────────────────────────────────
# SCENARIO 2 — Smurfing / Structuring
# PIX R$9.750 (below threshold), 7 tx in 24h, aggregate R$28.900 in 72h
# Expected: HIGH, STRUCTURING + ATYPICAL_FREQUENCY triggered, ESCALATE_FOR_REVIEW
# ─────────────────────────────────────────────

class TestScenario2Smurfing:

    @pytest.fixture(scope="class")
    def result(self, client, system_prompt):
        return classify_transaction(SCENARIO_2, client=client, prompt_override=system_prompt)

    def test_risk_level_high_or_critical(self, result):
        assert result["risk_level"] in {"HIGH", "CRITICAL"}, (
            f"Expected HIGH or CRITICAL for smurfing scenario, got {result['risk_level']}"
        )

    def test_risk_score_above_50(self, result):
        assert result["risk_score"] >= 50, (
            f"Smurfing score should be ≥50, got {result['risk_score']}"
        )

    def test_structuring_triggered(self, result):
        triggered = triggered_typologies(result)
        assert "STRUCTURING" in triggered, (
            f"STRUCTURING should be triggered. Triggered: {triggered}"
        )

    def test_atypical_frequency_triggered(self, result):
        triggered = triggered_typologies(result)
        assert "ATYPICAL_FREQUENCY" in triggered, (
            f"ATYPICAL_FREQUENCY should be triggered (7 tx in 24h for PF_STANDARD). "
            f"Triggered: {triggered}"
        )

    def test_action_is_escalate_or_coaf(self, result):
        assert result["recommended_action"] in {"ESCALATE_FOR_REVIEW", "COMMUNICATE_TO_COAF"}, (
            f"Expected escalation action, got {result['recommended_action']}"
        )

    def test_structuring_signals_reference_amount(self, result):
        """The STRUCTURING typology signals should mention the below-threshold amount."""
        for t in result["typologies_triggered"]:
            if t["typology"] == "STRUCTURING" and t["status"] == "TRIGGERED":
                signals_text = " ".join(t["signals_identified"]).lower()
                assert any(
                    kw in signals_text
                    for kw in ["9750", "9.750", "threshold", "8.000", "9.999", "below", "r$"]
                ), f"Structuring signals don't reference the amount: {t['signals_identified']}"

    def test_no_pep_triggered(self, result):
        triggered = triggered_typologies(result)
        assert "PEP_INVOLVEMENT" not in triggered, "PEP should NOT be triggered (no PEP in scenario 2)"


# ─────────────────────────────────────────────
# SCENARIO 3 — PEP + Cayman Islands (Tax Haven)
# Wire R$87.500, PEP sender, receiver in CYM (RFB tax haven), no purpose
# Expected: HIGH or CRITICAL, PEP_INVOLVEMENT + HIGH_RISK_GEOGRAPHY triggered
# ─────────────────────────────────────────────

class TestScenario3PepCayman:

    @pytest.fixture(scope="class")
    def result(self, client, system_prompt):
        return classify_transaction(SCENARIO_3, client=client, prompt_override=system_prompt)

    def test_risk_level_high_or_critical(self, result):
        assert result["risk_level"] in {"HIGH", "CRITICAL"}, (
            f"Expected HIGH or CRITICAL for PEP+Cayman scenario, got {result['risk_level']}"
        )

    def test_risk_score_above_50(self, result):
        assert result["risk_score"] >= 50, (
            f"PEP+Cayman score should be ≥50, got {result['risk_score']}"
        )

    def test_pep_involvement_triggered(self, result):
        triggered = triggered_typologies(result)
        assert "PEP_INVOLVEMENT" in triggered, (
            f"PEP_INVOLVEMENT should be triggered. Triggered: {triggered}"
        )

    def test_high_risk_geography_triggered(self, result):
        triggered = triggered_typologies(result)
        assert "HIGH_RISK_GEOGRAPHY" in triggered, (
            f"HIGH_RISK_GEOGRAPHY should be triggered (CYM = RFB tax haven). "
            f"Triggered: {triggered}"
        )

    def test_cayman_flagged_in_jurisdiction(self, result):
        codes = jurisdiction_codes(result)
        assert "CYM" in codes, (
            f"Cayman Islands (CYM) should appear in jurisdiction_flags. Got: {codes}"
        )

    def test_cayman_classified_as_tax_haven(self, result):
        for j in result.get("jurisdiction_flags", []):
            if j["jurisdiction_code"] == "CYM":
                lists = j["list_membership"]
                assert "RFB_TAX_HAVEN" in lists, (
                    f"CYM should be in RFB_TAX_HAVEN list. Got: {lists}"
                )

    def test_action_is_not_monitor(self, result):
        assert result["recommended_action"] != "MONITOR", (
            "PEP + tax haven should not result in MONITOR"
        )

    def test_no_structuring_triggered(self, result):
        """Amount R$87.500 is not in the structuring range (R$8k–R$9.9k)."""
        triggered = triggered_typologies(result)
        assert "STRUCTURING" not in triggered, (
            f"STRUCTURING should NOT be triggered for R$87.500. Triggered: {triggered}"
        )


# ─────────────────────────────────────────────
# CROSS-CUTTING — Output contract tests
# These run without API calls, validating the validate_result() function directly.
# ─────────────────────────────────────────────

class TestOutputContract:

    def test_validate_accepts_valid_result(self):
        from pipeline.classifier import validate_result
        valid = {
            "transaction_id": "TXN-TEST",
            "customer_profile_used": "PF_STANDARD",
            "risk_level": "LOW",
            "risk_score": 10,
            "typologies_triggered": [
                {
                    "typology": "STRUCTURING",
                    "status": "NOT_TRIGGERED",
                    "signals_identified": [],
                }
            ],
            "jurisdiction_flags": [],
            "narrative": "No suspicious activity detected.",
            "recommended_action": "MONITOR",
            "data_quality_flags": [],
            "disclaimer": "Synthetic data. Portfolio use only.",
        }
        result = validate_result(valid)
        assert result["risk_level"] == "LOW"

    def test_validate_rejects_invalid_risk_level(self):
        from pipeline.classifier import validate_result, ClassificationError
        bad = {
            "transaction_id": "X", "customer_profile_used": "PF_STANDARD",
            "risk_level": "EXTREME",   # invalid
            "risk_score": 99,
            "typologies_triggered": [], "jurisdiction_flags": [],
            "narrative": "x", "recommended_action": "MONITOR",
            "data_quality_flags": [], "disclaimer": "x",
        }
        with pytest.raises(ClassificationError, match="risk_level"):
            validate_result(bad)

    def test_validate_rejects_score_out_of_range(self):
        from pipeline.classifier import validate_result, ClassificationError
        bad = {
            "transaction_id": "X", "customer_profile_used": "PF_STANDARD",
            "risk_level": "HIGH", "risk_score": 150,   # out of range
            "typologies_triggered": [], "jurisdiction_flags": [],
            "narrative": "x", "recommended_action": "ESCALATE_FOR_REVIEW",
            "data_quality_flags": [], "disclaimer": "x",
        }
        with pytest.raises(ClassificationError, match="risk_score"):
            validate_result(bad)

    def test_validate_rejects_missing_keys(self):
        from pipeline.classifier import validate_result, ClassificationError
        with pytest.raises(ClassificationError, match="Missing keys"):
            validate_result({"transaction_id": "X", "risk_level": "LOW"})

    def test_parse_json_strips_markdown_fence(self):
        from pipeline.classifier import _parse_json
        raw = '```json\n{"risk_level": "LOW", "risk_score": 5}\n```'
        result = _parse_json(raw)
        assert result["risk_level"] == "LOW"

    def test_parse_json_handles_preamble(self):
        from pipeline.classifier import _parse_json
        raw = 'Here is the result:\n{"risk_level": "HIGH", "risk_score": 60}'
        result = _parse_json(raw)
        assert result["risk_score"] == 60
