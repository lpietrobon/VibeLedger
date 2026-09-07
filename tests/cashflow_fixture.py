"""Reusable CF-02 synthetic ledger seed and independently authored oracle."""
import json
from datetime import date
from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.models.models import Account, Item, Transaction, TransactionAnnotation, TransferPair
from app.services.security import encrypt_token

FIXTURE_PATH = Path(__file__).parents[1] / "docs/roadmap/epics/010-trustworthy-cashflow/artifacts/CF-02-ledger-fixture.json"


def cashflow_oracle():
    """Return fixture rows and expected totals without invoking production analytics."""
    return json.loads(FIXTURE_PATH.read_text())


def seed_cashflow_ledger(db):
    """Seed CF-02 evidence and return stable IDs plus its independent oracle."""
    oracle = cashflow_oracle()
    item = Item(plaid_item_id="cf02-fixture", access_token_encrypted=encrypt_token("fixture"), status="active")
    db.add(item)
    db.flush()
    accounts = {}
    for key, kind in oracle["accounts"].items():
        account = Account(plaid_account_id=f"cf02-{key}", item_id=item.id, name=key.title(), type=kind, currency=oracle["currency"])
        db.add(account)
        accounts[key] = account
    db.flush()
    rows = {}
    for row in oracle["rows"]:
        tx = Transaction(
            plaid_transaction_id=f"cf02-{row['id']}",
            account_id=accounts[row["account"]].id, item_id=item.id,
            date=date.fromisoformat(row["date"]), amount=row["amount"],
            name=row["id"], merchant_name=row["id"],
            plaid_category_primary=row["category"], pending=row["kind"] == "pending",
            raw_json=json.dumps({"iso_currency_code": oracle["currency"],
                                 "authorized_date": row.get("authorized_date")}),
        )
        db.add(tx)
        rows[row["id"]] = tx
    db.flush()
    pairs = {}
    for row in oracle["rows"]:
        if row.get("pair"):
            sides = pairs.setdefault(row["pair"], {})
            sides["out" if row["amount"] > 0 else "in"] = rows[row["id"]].id
        if row["category"]:
            db.add(TransactionAnnotation(
                transaction_id=rows[row["id"]].id, user_category=row["category"],
                refund_status="confirmed" if row["kind"] == "refund" else None,
                refund_match_transaction_id=(rows[row["refund_of"]].id
                                             if row.get("refund_of") else None),
            ))
    for sides in pairs.values():
        db.add(TransferPair(txn_out_id=sides["out"], txn_in_id=sides["in"], confirmed=True))
    db.flush()
    return {
        "item_id": item.id,
        "account_ids": {key: account.id for key, account in accounts.items()},
        "transaction_ids": {key: row.id for key, row in rows.items()},
        "oracle": oracle,
    }


@pytest.fixture
def cashflow_ledger():
    """Pytest fixture for future API scenarios that need the CF-02 ledger."""
    with SessionLocal() as db:
        seeded = seed_cashflow_ledger(db)
        db.commit()
        return seeded
