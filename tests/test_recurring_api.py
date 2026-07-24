from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import (
    Account,
    Item,
    Transaction,
    TransactionAnnotation,
    TransferPair,
)
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def _seed():
    """A monthly subscription, a one-off purchase, and a transfer pair."""
    with SessionLocal() as db:
        item = Item(plaid_item_id="i-rec", access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        checking = Account(plaid_account_id="a-rec-chk", item_id=item.id, name="Checking")
        credit = Account(plaid_account_id="a-rec-cc", item_id=item.id, name="Card")
        db.add_all([checking, credit])
        db.flush()

        tx_id = 0

        def add(account, d, amt, name, merchant=None, cat=None):
            nonlocal tx_id
            tx_id += 1
            t = Transaction(
                plaid_transaction_id=f"rec-{tx_id}",
                account_id=account.id,
                item_id=item.id,
                date=d,
                amount=amt,
                name=name,
                merchant_name=merchant,
                plaid_category_primary=cat,
                pending=False,
            )
            db.add(t)
            db.flush()
            return t

        # Monthly subscription across 6 months.
        for k in range(6):
            add(credit, date(2026, 1 + k, 12), 15.99, "SPOTIFY", "Spotify", "ENTERTAINMENT")

        # A single non-recurring purchase.
        add(credit, date(2026, 3, 3), 240.0, "Furniture Store", "Furniture Store", "GENERAL_MERCHANDISE")

        # A credit-card payment transfer pair — must be excluded from recurring.
        out = add(checking, date(2026, 2, 1), 500.0, "CC Payment")
        inn = add(credit, date(2026, 2, 1), -500.0, "CC Payment")
        db.add(TransferPair(txn_out_id=out.id, txn_in_id=inn.id, detected_by="manual", confirmed=True))
        db.commit()


def test_recurring_endpoint_finds_subscription():
    _seed()
    with TestClient(app) as client:
        r = client.get("/analytics/recurring", headers=AUTH_HEADERS, params={"end_date": "2026-06-30"})
    assert r.status_code == 200
    body = r.json()
    labels = {item["merchant_label"]: item for item in body["items"]}

    assert "Spotify" in labels
    spotify = labels["Spotify"]
    assert spotify["cadence"] == "monthly"
    assert spotify["occurrences"] == 6
    assert spotify["average_amount"] == 15.99

    # One-off purchase and the transfer pair must not appear.
    assert "Furniture Store" not in labels
    assert "CC Payment" not in labels

    assert body["summary"]["count"] == 1
    assert body["summary"]["active_monthly_estimate"] == spotify["monthly_estimate"]


def test_recurring_endpoint_respects_transfer_override():
    _seed()
    with SessionLocal() as db:
        # Flag every Spotify charge as a manual transfer override.
        spotify_ids = [
            t.id for t in db.query(Transaction).filter(Transaction.merchant_name == "Spotify").all()
        ]
        for tid in spotify_ids:
            db.add(TransactionAnnotation(transaction_id=tid, is_transfer_override=True))
        db.commit()

    with TestClient(app) as client:
        r = client.get("/analytics/recurring", headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json()["items"] == []
