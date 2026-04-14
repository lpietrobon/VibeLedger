from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction, TransactionAnnotation, TransferPair
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def _seed_transfer_ledger():
    """Seed two accounts with a matching outflow/inflow pair plus a regular spend."""
    with SessionLocal() as db:
        item = Item(plaid_item_id="i-xfer", access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        checking = Account(
            plaid_account_id="a-check",
            item_id=item.id,
            name="Checking",
            type="depository",
            subtype="checking",
            current_balance=Decimal("1000.00"),
        )
        credit = Account(
            plaid_account_id="a-credit",
            item_id=item.id,
            name="CC",
            type="credit",
            subtype="credit card",
            current_balance=Decimal("300.00"),
        )
        db.add_all([checking, credit])
        db.flush()

        # CC payment: $200 out of checking, $200 in on credit (same date)
        db.add(Transaction(
            plaid_transaction_id="tx-out", account_id=checking.id, item_id=item.id,
            date=date(2026, 3, 15), amount=Decimal("200.00"), name="CC PMT",
            plaid_category_primary="TRANSFER", pending=False,
        ))
        db.add(Transaction(
            plaid_transaction_id="tx-in", account_id=credit.id, item_id=item.id,
            date=date(2026, 3, 15), amount=Decimal("-200.00"), name="Payment received",
            plaid_category_primary="TRANSFER", pending=False,
        ))
        # Regular spend that should always stay counted
        db.add(Transaction(
            plaid_transaction_id="tx-spend", account_id=checking.id, item_id=item.id,
            date=date(2026, 3, 20), amount=Decimal("50.00"), name="Groceries",
            plaid_category_primary="FOOD_AND_DRINK", pending=False,
        ))
        db.commit()
        return checking.id, credit.id


def test_accounts_summary_groups_and_net_worth():
    _seed_transfer_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/accounts-summary", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["assets"] == 1000.0
    assert data["liabilities"] == 300.0
    assert data["net_worth"] == 700.0
    assert set(data["groups"].keys()) == {"depository", "credit"}


def test_transfers_detect_and_list():
    _seed_transfer_ledger()
    with TestClient(app) as client:
        r = client.post("/transfers/detect", headers=AUTH_HEADERS)
        assert r.status_code == 200
        assert r.json()["created"] == 1

        r = client.get("/transfers", headers=AUTH_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["amount"] == 200.0
        assert body["items"][0]["detected_by"] == "auto"
        assert body["items"][0]["confirmed"] is False


def test_analytics_excludes_transfers_by_default():
    _seed_transfer_ledger()
    with TestClient(app) as client:
        # Before detection: the $200 transfer is counted as spend
        r = client.get("/analytics/monthly-spend", headers=AUTH_HEADERS)
        assert r.json() == [{"month": "2026-03", "spend": 250.0}]

        client.post("/transfers/detect", headers=AUTH_HEADERS)

        # After detection: transfer is excluded, only the $50 spend remains
        r = client.get("/analytics/monthly-spend", headers=AUTH_HEADERS)
        assert r.json() == [{"month": "2026-03", "spend": 50.0}]

        # include_transfers=true restores the old behavior
        r = client.get(
            "/analytics/monthly-spend",
            params={"include_transfers": "true"},
            headers=AUTH_HEADERS,
        )
        assert r.json() == [{"month": "2026-03", "spend": 250.0}]


def test_cashflow_excludes_transfer_both_sides():
    _seed_transfer_ledger()
    with TestClient(app) as client:
        client.post("/transfers/detect", headers=AUTH_HEADERS)
        r = client.get("/analytics/cashflow-trend", headers=AUTH_HEADERS)
    data = {row["month"]: row for row in r.json()}
    # Transfer's $200 income side AND $200 expense side should both be gone
    assert data["2026-03"]["income"] == 0.0
    assert data["2026-03"]["expenses"] == 50.0
    assert data["2026-03"]["net"] == -50.0


def test_transfer_override_excludes_txn():
    _seed_transfer_ledger()
    with SessionLocal() as db:
        tx = db.query(Transaction).filter(Transaction.name == "Groceries").first()
        db.add(TransactionAnnotation(transaction_id=tx.id, is_transfer_override=True))
        db.commit()
    with TestClient(app) as client:
        r = client.get("/analytics/monthly-spend", headers=AUTH_HEADERS)
    # The only un-overridden spend was the $200 transfer, still counted (no pair yet)
    assert r.json() == [{"month": "2026-03", "spend": 200.0}]


def test_transfers_confirm_and_delete():
    _seed_transfer_ledger()
    with TestClient(app) as client:
        client.post("/transfers/detect", headers=AUTH_HEADERS)
        pair_id = client.get("/transfers", headers=AUTH_HEADERS).json()["items"][0]["id"]

        r = client.post(f"/transfers/{pair_id}/confirm", headers=AUTH_HEADERS)
        assert r.status_code == 200
        assert r.json()["confirmed"] is True

        r = client.delete(f"/transfers/{pair_id}", headers=AUTH_HEADERS)
        assert r.status_code == 200

        # Re-detect now works again — proves idempotent removal
        r = client.post("/transfers/detect", headers=AUTH_HEADERS)
        assert r.json()["created"] == 1


def test_manual_pair_validates_amounts_and_accounts():
    checking_id, credit_id = _seed_transfer_ledger()
    with SessionLocal() as db:
        out = db.query(Transaction).filter_by(plaid_transaction_id="tx-out").one()
        inn = db.query(Transaction).filter_by(plaid_transaction_id="tx-in").one()
        spend = db.query(Transaction).filter_by(plaid_transaction_id="tx-spend").one()
        out_id, in_id, spend_id = out.id, inn.id, spend.id

    with TestClient(app) as client:
        # amount mismatch (200 vs 50)
        r = client.post("/transfers", json={"txn_a_id": out_id, "txn_b_id": spend_id}, headers=AUTH_HEADERS)
        assert r.status_code == 400

        # valid manual pair
        r = client.post("/transfers", json={"txn_a_id": out_id, "txn_b_id": in_id}, headers=AUTH_HEADERS)
        assert r.status_code == 200

        # cannot pair an already-paired txn
        r = client.post("/transfers", json={"txn_a_id": out_id, "txn_b_id": in_id}, headers=AUTH_HEADERS)
        assert r.status_code == 400


def test_transfers_unauth():
    with TestClient(app) as client:
        assert client.get("/transfers").status_code == 401
        assert client.post("/transfers/detect").status_code == 401
        assert client.get("/analytics/accounts-summary").status_code == 401
