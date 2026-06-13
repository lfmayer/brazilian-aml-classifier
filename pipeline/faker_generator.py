"""
pipeline/faker_generator.py
Generates synthetic Brazilian financial transactions for AML testing.
All data is entirely fictitious. No real customer information is used.
"""

import json
import random
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker

fake = Faker("pt_BR")
random.seed(42)

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "synthetic_transactions.json"

# ─────────────────────────────────────────────
# JURISDICTION POOLS
# ─────────────────────────────────────────────
DOMESTIC = ["BRA"]
FATF_BLACKLIST = ["IRN", "PRK", "MMR"]
FATF_GREYLIST  = ["VEN", "NGA", "PHL", "SYR", "YEM", "LBN", "KEN", "BOL"]
TAX_HAVENS     = ["CYM", "PAN", "BHS", "BMU", "VGB", "LIE", "MCO", "AND"]
CLEAN_FOREIGN  = ["USA", "DEU", "GBR", "FRA", "CAN", "AUS", "JPN", "CHE"]

def pick_jurisdiction(risk_profile: str) -> str:
    if risk_profile == "clean":
        return random.choice(DOMESTIC * 8 + CLEAN_FOREIGN)
    if risk_profile == "medium":
        return random.choice(FATF_GREYLIST + TAX_HAVENS)
    if risk_profile == "high":
        return random.choice(FATF_BLACKLIST)
    return "BRA"

# ─────────────────────────────────────────────
# CUSTOMER PROFILES
# ─────────────────────────────────────────────
PROFILES = ["PF_STANDARD", "PF_HIGH_INCOME", "PJ_SME", "PJ_LARGE"]

PROFILE_DAILY_NORMAL = {
    "PF_STANDARD":   3,
    "PF_HIGH_INCOME": 10,
    "PJ_SME":        15,
    "PJ_LARGE":      40,
}

PROFILE_AMT_RANGE = {
    "PF_STANDARD":   (200,    8_000),
    "PF_HIGH_INCOME": (1_000, 80_000),
    "PJ_SME":        (500,   50_000),
    "PJ_LARGE":      (5_000, 500_000),
}

TX_TYPES = ["PIX", "PIX", "PIX", "TED", "DOC", "CASH_DEPOSIT", "WIRE_TRANSFER"]

PURPOSES = [
    "Pagamento de aluguel mensal",
    "Serviços prestados",
    "Transferência entre contas próprias",
    "Pagamento de fornecedor",
    "Reembolso de despesas",
    None, None,  # missing purpose is intentionally common
]

# ─────────────────────────────────────────────
# HASH HELPER
# ─────────────────────────────────────────────
def fake_hash(prefix: str, seed: str) -> str:
    h = hashlib.md5(seed.encode()).hexdigest()[:8].upper()
    return f"{prefix}-HASH-{h}"

# ─────────────────────────────────────────────
# SCENARIO BUILDERS
# ─────────────────────────────────────────────

def make_clean_transaction(tx_num: int) -> dict:
    profile = random.choice(PROFILES)
    lo, hi  = PROFILE_AMT_RANGE[profile]
    amount  = round(random.uniform(lo, hi * 0.6), 2)  # well below threshold range
    sender_seed = fake.cpf()

    return {
        "transaction_id": f"TXN-{tx_num:05d}",
        "transaction_timestamp": (
            datetime.now() - timedelta(days=random.randint(0, 30),
                                       hours=random.randint(0, 23))
        ).strftime("%Y-%m-%dT%H:%M:%S-03:00"),
        "transaction_type": random.choice(TX_TYPES),
        "direction": random.choice(["INBOUND", "OUTBOUND"]),
        "amount_brl": amount,
        "purpose_description": random.choice(PURPOSES),
        "sender_type": "CPF",
        "sender_id_hash": fake_hash("CPF", sender_seed),
        "sender_is_pep": False,
        "sender_jurisdiction": "BRA",
        "customer_profile": profile,
        "receiver_type": random.choice(["CPF", "CNPJ"]),
        "receiver_id_hash": fake_hash("CNPJ" if random.random() > 0.5 else "CPF", fake.cnpj()),
        "receiver_is_pep": False,
        "receiver_jurisdiction": "BRA",
        "transactions_last_24h_same_sender": random.randint(1, PROFILE_DAILY_NORMAL[profile]),
        "transactions_last_72h_same_sender": random.randint(1, PROFILE_DAILY_NORMAL[profile] * 2),
        "total_amount_last_72h_same_sender_brl": round(amount * random.uniform(1.5, 3), 2),
        "avg_monthly_amount_brl": round(amount * random.uniform(8, 20), 2),
    }


def make_structuring_transaction(tx_num: int) -> dict:
    """Amount just below R$10k + elevated 72h frequency."""
    sender_seed = fake.cpf()
    amount = round(random.uniform(8_000, 9_999), 2)
    n_72h  = random.randint(3, 6)
    total_72h = round(amount * n_72h * random.uniform(0.9, 1.1), 2)

    return {
        "transaction_id": f"TXN-{tx_num:05d}",
        "transaction_timestamp": (
            datetime.now() - timedelta(hours=random.randint(0, 72))
        ).strftime("%Y-%m-%dT%H:%M:%S-03:00"),
        "transaction_type": "PIX",
        "direction": "OUTBOUND",
        "amount_brl": amount,
        "purpose_description": None,
        "sender_type": "CPF",
        "sender_id_hash": fake_hash("CPF", sender_seed),
        "sender_is_pep": False,
        "sender_jurisdiction": "BRA",
        "customer_profile": "PF_STANDARD",
        "receiver_type": "CNPJ",
        "receiver_id_hash": fake_hash("CNPJ", fake.cnpj()),
        "receiver_is_pep": False,
        "receiver_jurisdiction": "BRA",
        "transactions_last_24h_same_sender": random.randint(5, 8),
        "transactions_last_72h_same_sender": n_72h,
        "total_amount_last_72h_same_sender_brl": total_72h,
        "avg_monthly_amount_brl": round(random.uniform(3_000, 6_000), 2),
    }


def make_pep_offshore_transaction(tx_num: int) -> dict:
    """PEP sender + tax haven receiver — canonical HIGH/CRITICAL."""
    sender_seed = fake.cpf()
    profile = random.choice(["PF_HIGH_INCOME", "PJ_SME"])
    lo, hi  = PROFILE_AMT_RANGE[profile]
    amount  = round(random.uniform(hi * 0.4, hi), 2)

    return {
        "transaction_id": f"TXN-{tx_num:05d}",
        "transaction_timestamp": (
            datetime.now() - timedelta(days=random.randint(0, 7))
        ).strftime("%Y-%m-%dT%H:%M:%S-03:00"),
        "transaction_type": "WIRE_TRANSFER",
        "direction": "OUTBOUND",
        "amount_brl": amount,
        "purpose_description": None,
        "sender_type": "CPF",
        "sender_id_hash": fake_hash("CPF", sender_seed),
        "sender_is_pep": True,
        "sender_jurisdiction": "BRA",
        "customer_profile": profile,
        "receiver_type": "CNPJ",
        "receiver_id_hash": fake_hash("CNPJ", fake.cnpj()),
        "receiver_is_pep": False,
        "receiver_jurisdiction": pick_jurisdiction("medium"),
        "transactions_last_24h_same_sender": random.randint(1, 4),
        "transactions_last_72h_same_sender": random.randint(2, 6),
        "total_amount_last_72h_same_sender_brl": round(amount * random.uniform(1.2, 3), 2),
        "avg_monthly_amount_brl": round(amount * random.uniform(0.5, 2), 2),
    }


def make_blacklist_transaction(tx_num: int) -> dict:
    """Any involvement of FATF blacklist jurisdiction = immediate CRITICAL signal."""
    sender_seed = fake.cpf()
    amount = round(random.uniform(5_000, 200_000), 2)

    return {
        "transaction_id": f"TXN-{tx_num:05d}",
        "transaction_timestamp": (
            datetime.now() - timedelta(days=random.randint(0, 14))
        ).strftime("%Y-%m-%dT%H:%M:%S-03:00"),
        "transaction_type": "WIRE_TRANSFER",
        "direction": random.choice(["INBOUND", "OUTBOUND"]),
        "amount_brl": amount,
        "purpose_description": None,
        "sender_type": random.choice(["CPF", "CNPJ"]),
        "sender_id_hash": fake_hash("CPF", sender_seed),
        "sender_is_pep": random.choice([True, False]),
        "sender_jurisdiction": random.choice([pick_jurisdiction("high"), "BRA"]),
        "customer_profile": random.choice(PROFILES),
        "receiver_type": "CNPJ",
        "receiver_id_hash": fake_hash("CNPJ", fake.cnpj()),
        "receiver_is_pep": False,
        "receiver_jurisdiction": pick_jurisdiction("high"),
        "transactions_last_24h_same_sender": random.randint(1, 5),
        "transactions_last_72h_same_sender": random.randint(1, 8),
        "total_amount_last_72h_same_sender_brl": round(amount * random.uniform(1, 3), 2),
        "avg_monthly_amount_brl": None,
    }

# ─────────────────────────────────────────────
# MAIN GENERATOR
# ─────────────────────────────────────────────

def generate_dataset(n: int = 100) -> list[dict]:
    """
    Generate n synthetic transactions with a realistic distribution:
      60% clean, 20% structuring, 12% PEP+offshore, 8% blacklist
    """
    transactions = []
    counters = {"clean": 0, "struct": 0, "pep": 0, "black": 0}

    weights = ["clean"] * 60 + ["struct"] * 20 + ["pep"] * 12 + ["black"] * 8
    random.shuffle(weights)

    for i, scenario in enumerate(weights[:n], start=1):
        if scenario == "clean":
            tx = make_clean_transaction(i)
            counters["clean"] += 1
        elif scenario == "struct":
            tx = make_structuring_transaction(i)
            counters["struct"] += 1
        elif scenario == "pep":
            tx = make_pep_offshore_transaction(i)
            counters["pep"] += 1
        else:
            tx = make_blacklist_transaction(i)
            counters["black"] += 1

        transactions.append(tx)

    print(f"Generated {n} transactions: {counters}")
    return transactions


if __name__ == "__main__":
    dataset = generate_dataset(100)
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(dataset, indent=2, ensure_ascii=False))
    print(f"Saved to {OUTPUT_PATH}")
