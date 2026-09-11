"""Synthetic PI-13 category-drilldown fixture and independent oracle."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.models.models import Account, Item, Transaction, TransactionAnnotation, TransferPair
from app.services.security import encrypt_token


FIXTURE_PATH = Path(__file__).parents[1] / "docs/roadmap/epics/020-product-integrity/artifacts/PI-13-category-drilldown-fixture.json"


def category_drilldown_oracle():
    return json.loads(FIXTURE_PATH.read_text())


def seed_category_drilldown_ledger(db):
    oracle = category_drilldown_oracle()
    item = Item(
        plaid_item_id="pi13-category-item",
        access_token_encrypted=encrypt_token("pi13-category-token"),
        status="active",
    )
    db.add(item)
    db.flush()
    checking = Account(
        plaid_account_id="pi13-category-checking",
        item_id=item.id,
        name="PI13 Checking",
        type="depository",
        subtype="checking",
        mask="1313",
        currency=oracle["currency"],
    )
    card = Account(
        plaid_account_id="pi13-category-card",
        item_id=item.id,
        name="PI13 Card",
        type="credit",
        subtype="credit card",
        mask="1314",
        currency=oracle["currency"],
    )
    db.add_all([checking, card])
    db.flush()

    rows = {}
    for row in oracle["rows"]:
        account = checking if row["id"] in {"candidate-out", "confirmed-out", "shopping-charge"} else card
        tx = Transaction(
            plaid_transaction_id=f"pi13-{row['id']}",
            item_id=item.id,
            account_id=account.id,
            date=date.fromisoformat(row["date"]),
            amount=Decimal(str(row["amount"])),
            name=row["id"],
            merchant_name=row["id"],
            plaid_category_primary="FOOD_AND_DRINK",
            pending=row["state"] == "pending",
            raw_json=json.dumps({"iso_currency_code": oracle["currency"]}),
        )
        db.add(tx)
        db.flush()
        rows[row["id"]] = tx
        if row["category"] != "FOOD/OTHER":
            db.add(TransactionAnnotation(transaction_id=tx.id, user_category=row["category"]))
        elif row["state"] == "confirmed-refund":
            db.add(TransactionAnnotation(
                transaction_id=tx.id,
                refund_status="confirmed",
                refund_match_transaction_id=rows[row["refund_of"]].id,
            ))
        elif row["state"] in {"unconfirmed-candidate", "confirmed-transfer"}:
            db.add(TransactionAnnotation(transaction_id=tx.id, user_category=row["category"]))

    db.flush()
    for pair_name, confirmed in (("candidate", False), ("confirmed", True)):
        out = rows[f"{pair_name}-out"]
        incoming = rows[f"{pair_name}-in"]
        db.add(TransferPair(
            txn_out_id=out.id,
            txn_in_id=incoming.id,
            confirmed=confirmed,
            detected_by="pi13-fixture",
        ))
    db.commit()
    return {
        "transaction_ids": {key: row.id for key, row in rows.items()},
        "oracle": oracle,
    }


@pytest.fixture
def category_drilldown_ledger():
    with SessionLocal() as db:
        return seed_category_drilldown_ledger(db)
