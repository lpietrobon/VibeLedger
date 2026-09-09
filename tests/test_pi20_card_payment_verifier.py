"""Independent PI-20 checks for the PI-07 card-payment correction.

These tests are deliberately separate from the frozen PI-19 oracle.  They
exercise the boundaries around the RCA-shaped exception: evidence must be
present on both legs, account roles must be checking -> credit card, reverse
posting must stay within four days, and ambiguous alternatives must remain
unpaired.
"""

from datetime import date, timedelta
from decimal import Decimal

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction, TransactionAnnotation, TransferPair
from app.services import transfer_detector
from tests.conftest import AUTH_HEADERS
from fastapi.testclient import TestClient


PAYMENT_CATEGORY = "FINANCE/CREDIT_CARD_PAYMENT"


def _ledger(db, *, second_card=False):
    item = Item(
        plaid_item_id="pi20-item",
        access_token_encrypted="synthetic-token",
        status="active",
    )
    db.add(item)
    db.flush()
    checking = Account(
        plaid_account_id="pi20-checking",
        item_id=item.id,
        name="Checking",
        type="depository",
        subtype="checking",
        currency="USD",
    )
    card = Account(
        plaid_account_id="pi20-card-a",
        item_id=item.id,
        name="Card A",
        type="credit",
        subtype="credit card",
        currency="USD",
    )
    db.add_all([checking, card])
    if second_card:
        db.add(Account(
            plaid_account_id="pi20-card-b",
            item_id=item.id,
            name="Card B",
            type="credit",
            subtype="credit card",
            currency="USD",
        ))
    db.flush()
    return item, checking, card


def _tx(db, *, item, account, key, when, amount, name):
    row = Transaction(
        plaid_transaction_id=f"pi20-{key}",
        item_id=item.id,
        account_id=account.id,
        date=when,
        amount=Decimal(str(amount)),
        name=name,
        pending=False,
    )
    db.add(row)
    db.flush()
    return row


def _payment_evidence(db, *rows):
    db.add_all([
        TransactionAnnotation(transaction_id=row.id, rule_category=PAYMENT_CATEGORY)
        for row in rows
    ])
    db.flush()


def test_reverse_exception_requires_payment_evidence_on_both_legs():
    with SessionLocal() as db:
        item, checking, card = _ledger(db)
        credit = _tx(db, item=item, account=card, key="credit", when=date(2034, 1, 10), amount=-100, name="Card receipt")
        outflow = _tx(db, item=item, account=checking, key="outflow", when=date(2034, 1, 12), amount=100, name="Card autopay")
        _payment_evidence(db, outflow)
        db.commit()

        assert transfer_detector.detect_candidates(db) == []


def test_reverse_exception_does_not_cross_checking_to_savings_roles():
    with SessionLocal() as db:
        item, checking, card = _ledger(db)
        savings = Account(
            plaid_account_id="pi20-savings",
            item_id=item.id,
            name="Savings",
            type="depository",
            subtype="savings",
            currency="USD",
        )
        db.add(savings)
        db.flush()
        receipt = _tx(db, item=item, account=savings, key="savings-receipt", when=date(2034, 1, 10), amount=-100, name="Payment received")
        outflow = _tx(db, item=item, account=checking, key="savings-outflow", when=date(2034, 1, 12), amount=100, name="Autopay")
        _payment_evidence(db, receipt, outflow)
        db.commit()

        assert transfer_detector.detect_candidates(db) == []


def test_two_equally_close_qualified_card_candidates_remain_unpaired():
    with SessionLocal() as db:
        item, checking, card_a = _ledger(db, second_card=True)
        card_b = db.query(Account).filter(Account.plaid_account_id == "pi20-card-b").one()
        receipt_a = _tx(db, item=item, account=card_a, key="receipt-a", when=date(2034, 1, 10), amount=-100, name="Payment received A")
        receipt_b = _tx(db, item=item, account=card_b, key="receipt-b", when=date(2034, 1, 14), amount=-100, name="Payment received B")
        outflow = _tx(db, item=item, account=checking, key="outflow", when=date(2034, 1, 12), amount=100, name="Card autopay")
        _payment_evidence(db, receipt_a, receipt_b, outflow)
        db.commit()

        assert transfer_detector.detect_candidates(db) == []
        assert db.query(TransferPair).count() == 0


def test_forward_order_matching_still_uses_requested_detector_window():
    with SessionLocal() as db:
        item, checking, card = _ledger(db)
        outflow = _tx(db, item=item, account=checking, key="forward-outflow", when=date(2034, 1, 10), amount=100, name="Ordinary transfer")
        receipt = _tx(db, item=item, account=card, key="forward-receipt", when=date(2034, 1, 14), amount=-100, name="Ordinary receipt")
        db.commit()

        assert transfer_detector.detect_candidates(db, window_days=3) == []
        created = transfer_detector.detect_candidates(db, window_days=4)
        assert len(created) == 1
        assert created[0].confirmed is False


def test_reverse_exception_is_bounded_even_with_wide_requested_window():
    with SessionLocal() as db:
        item, checking, card = _ledger(db)
        receipt = _tx(db, item=item, account=card, key="late-receipt", when=date(2034, 1, 10), amount=-100, name="Card payment received")
        outflow = _tx(db, item=item, account=checking, key="late-outflow", when=date(2034, 1, 15), amount=100, name="Card autopay")
        _payment_evidence(db, receipt, outflow)
        db.commit()

        assert transfer_detector.detect_candidates(db, window_days=14) == []


def test_candidate_is_counted_until_confirmation_then_purchase_remains_once():
    bounds = {"start_date": "2034-01-01", "end_date": "2034-01-31"}
    with SessionLocal() as db:
        item, checking, card = _ledger(db)
        purchase = _tx(db, item=item, account=card, key="purchase", when=date(2034, 1, 8), amount=30, name="Synthetic purchase")
        receipt = _tx(db, item=item, account=card, key="receipt", when=date(2034, 1, 10), amount=-100, name="Card payment received")
        outflow = _tx(db, item=item, account=checking, key="payment", when=date(2034, 1, 12), amount=100, name="Card autopay")
        _payment_evidence(db, receipt, outflow)
        db.commit()
        purchase_id, receipt_id, outflow_id = purchase.id, receipt.id, outflow.id

    with TestClient(app) as client:
        detected = client.post("/transfers/detect", headers=AUTH_HEADERS)
        assert detected.status_code == 200
        assert detected.json()["created"] == 1

        before = client.get("/analytics/cashflow-sankey", params=bounds, headers=AUTH_HEADERS).json()
        candidate_rows = client.get("/transactions", params=bounds, headers=AUTH_HEADERS).json()["items"]
        assert before["income"] == 100.0
        assert before["total_spend"] == 130.0
        assert next(row for row in candidate_rows if row["id"] == receipt_id)["is_transfer_candidate"] is True
        pair_id = client.get("/transfers", headers=AUTH_HEADERS).json()["items"][0]["id"]
        confirmed = client.post(f"/transfers/{pair_id}/confirm", headers=AUTH_HEADERS)
        assert confirmed.status_code == 200

        after = client.get("/analytics/cashflow-sankey", params=bounds, headers=AUTH_HEADERS).json()
        rows = client.get("/transactions", params=bounds, headers=AUTH_HEADERS).json()["items"]

    assert after["income"] == 0.0
    assert after["total_spend"] == 30.0
    assert all(
        row["is_transfer"] is True
        for row in rows
        if row["id"] in {receipt_id, outflow_id}
    )
    assert next(row for row in rows if row["id"] == purchase_id)["is_transfer"] is False
