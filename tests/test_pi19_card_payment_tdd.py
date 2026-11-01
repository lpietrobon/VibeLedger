"""PI-19 red contract for the diagnosed card-payment transfer gap.

All dates, amounts, labels, and identifiers in this module are synthetic.  The
fixture preserves only the structural shape observed during PI-06:

* a credit-card payment credit can post before its checking-account outflow;
* strong payment evidence distinguishes that shape from a generic equal-amount
  collision; and
* a payment with no covered counterpart must remain unpaired and counted while
  reporting continues to disclose unverified history coverage.

Product code must make the first two tests pass without weakening the existing
generic reverse-order collision test in ``test_transfer_detector.py``.
"""

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction, TransactionAnnotation, TransferPair
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


PAYMENT_CATEGORY = "FINANCE/CREDIT_CARD_PAYMENT"
BOUNDS = {"start_date": "2031-01-01", "end_date": "2031-01-31"}


def _seed_accounts(db):
    item = Item(
        plaid_item_id="pi19-synthetic-item",
        access_token_encrypted=encrypt_token("synthetic-token"),
        status="active",
    )
    db.add(item)
    db.flush()
    checking = Account(
        plaid_account_id="pi19-synthetic-checking",
        item_id=item.id,
        name="Synthetic checking",
        type="depository",
        subtype="checking",
        currency="USD",
    )
    card = Account(
        plaid_account_id="pi19-synthetic-card",
        item_id=item.id,
        name="Synthetic card",
        type="credit",
        subtype="credit card",
        currency="USD",
    )
    db.add_all([checking, card])
    db.flush()
    return item, checking, card


def _add_transaction(db, *, item, account, key, when, amount, name, category):
    transaction = Transaction(
        plaid_transaction_id=f"pi19-{key}",
        item_id=item.id,
        account_id=account.id,
        date=when,
        amount=Decimal(str(amount)),
        name=name,
        plaid_category_primary=category,
        pending=False,
    )
    db.add(transaction)
    db.flush()
    return transaction


def _mark_as_card_payment(db, *transactions):
    for transaction in transactions:
        db.add(TransactionAnnotation(
            transaction_id=transaction.id,
            rule_category=PAYMENT_CATEGORY,
        ))


def _seed_reverse_order_repayment():
    """Return ids for a wholly synthetic, evidence-qualified repayment."""
    with SessionLocal() as db:
        item, checking, card = _seed_accounts(db)
        purchase = _add_transaction(
            db,
            item=item,
            account=card,
            key="purchase",
            when=date(2031, 1, 8),
            amount="37.00",
            name="Synthetic grocery purchase",
            category="FOOD_AND_DRINK",
        )
        card_credit = _add_transaction(
            db,
            item=item,
            account=card,
            key="card-credit",
            when=date(2031, 1, 10),
            amount="-90.00",
            name="Synthetic card payment received",
            category="LOAN_PAYMENTS",
        )
        checking_outflow = _add_transaction(
            db,
            item=item,
            account=checking,
            key="checking-outflow",
            when=date(2031, 1, 12),
            amount="90.00",
            name="Synthetic card autopay",
            category="LOAN_PAYMENTS",
        )
        _mark_as_card_payment(db, card_credit, checking_outflow)
        db.commit()
        return {
            "purchase": purchase.id,
            "card_credit": card_credit.id,
            "checking_outflow": checking_outflow.id,
        }


def _category_amount(sankey, category):
    return sum(
        row["amount"]
        for bucket in sankey["buckets"]
        for row in bucket["categories"]
        if row["category"] == category
    )


def test_evidence_qualified_card_repayment_is_detected_when_card_credit_posts_first():
    """A reverse posting order is valid only for a qualified card repayment."""
    ids = _seed_reverse_order_repayment()

    with TestClient(app) as client:
        detected = client.post("/transfers/detect", headers=AUTH_HEADERS)
        assert detected.status_code == 200
        assert detected.json()["created"] == 1

        activity = client.get(
            "/transactions",
            params={**BOUNDS, "category": PAYMENT_CATEGORY},
            headers=AUTH_HEADERS,
        ).json()["items"]

    assert {row["id"] for row in activity} == {
        ids["card_credit"],
        ids["checking_outflow"],
    }
    assert all(row["is_transfer_candidate"] for row in activity)
    assert not any(row["is_transfer"] for row in activity)


def test_reverse_order_card_repayment_can_be_reviewed_and_confirmed():
    """Review must be able to confirm the same evidence accepted by detection."""
    ids = _seed_reverse_order_repayment()
    with SessionLocal() as db:
        pair = TransferPair(
            txn_out_id=ids["checking_outflow"],
            txn_in_id=ids["card_credit"],
            detected_by="auto",
            confirmed=False,
        )
        db.add(pair)
        db.commit()
        pair_id = pair.id

    with TestClient(app) as client:
        before = client.get(
            "/analytics/cashflow-sankey", params=BOUNDS, headers=AUTH_HEADERS
        ).json()
        assert _category_amount(before, PAYMENT_CATEGORY) == 90.0

        confirmed = client.post(f"/transfers/{pair_id}/confirm", headers=AUTH_HEADERS)
        assert confirmed.status_code == 200
        assert confirmed.json()["confirmed"] is True

        after = client.get(
            "/analytics/cashflow-sankey", params=BOUNDS, headers=AUTH_HEADERS
        ).json()
        activity = client.get(
            "/transactions", params=BOUNDS, headers=AUTH_HEADERS
        ).json()["items"]

    assert _category_amount(after, PAYMENT_CATEGORY) == 0
    assert after["total_spend"] == 37.0
    repayment_rows = [
        row for row in activity
        if row["id"] in {ids["card_credit"], ids["checking_outflow"]}
    ]
    assert all(row["is_transfer"] for row in repayment_rows)


def test_payment_without_a_covered_counterpart_stays_unpaired_and_counted():
    """Coverage uncertainty must never invent or silently suppress a transfer."""
    with SessionLocal() as db:
        item, checking, _ = _seed_accounts(db)
        unmatched = _add_transaction(
            db,
            item=item,
            account=checking,
            key="unmatched-payment",
            when=date(2031, 1, 15),
            amount="45.00",
            name="Synthetic payment with no linked counterpart",
            category="LOAN_PAYMENTS",
        )
        _mark_as_card_payment(db, unmatched)
        db.commit()
        unmatched_id = unmatched.id

    with TestClient(app) as client:
        detected = client.post("/transfers/detect", headers=AUTH_HEADERS)
        assert detected.status_code == 200
        assert detected.json()["created"] == 0

        sankey = client.get(
            "/analytics/cashflow-sankey", params=BOUNDS, headers=AUTH_HEADERS
        ).json()
        activity = client.get(
            "/transactions", params=BOUNDS, headers=AUTH_HEADERS
        ).json()["items"]

    assert _category_amount(sankey, PAYMENT_CATEGORY) == 45.0
    assert sankey["reporting"]["history_coverage"] == "unverified"
    row = next(row for row in activity if row["id"] == unmatched_id)
    assert row["transfer_pair_id"] is None
    assert row["is_transfer"] is False
    assert row["is_transfer_candidate"] is False
