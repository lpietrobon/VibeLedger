"""Implementation-only PI-28 coverage; PI-27's TDD contract remains untouched."""
from datetime import date
from decimal import Decimal
import json

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction
from app.services import transfer_detector
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def _seed(*, inactive=False):
    db = SessionLocal()
    item = Item(
        plaid_item_id="pi28-item",
        access_token_encrypted=encrypt_token("synthetic"),
        status="error" if inactive else "active",
    )
    db.add(item)
    db.flush()
    checking = Account(plaid_account_id="pi28-checking", item_id=item.id, name="Checking", currency="USD")
    savings = Account(plaid_account_id="pi28-savings", item_id=item.id, name="Savings", currency="USD")
    db.add_all([checking, savings])
    db.flush()
    detail = json.dumps({"personal_finance_category": {"detailed": "TRANSFER_OUT"}})
    out = Transaction(plaid_transaction_id="pi28-out", item_id=item.id, account_id=checking.id, date=date(2033, 1, 1), amount=Decimal("20"), name="move out", raw_json=detail)
    detail_in = json.dumps({"personal_finance_category": {"detailed": "TRANSFER_IN"}})
    inn = Transaction(plaid_transaction_id="pi28-in", item_id=item.id, account_id=savings.id, date=date(2033, 1, 2), amount=Decimal("-20"), name="move in", raw_json=detail_in)
    db.add_all([out, inn])
    db.commit()
    return db, out, inn


def test_inactive_linked_history_never_becomes_a_transfer_candidate():
    db, _, _ = _seed(inactive=True)
    try:
        assert transfer_detector.detect_candidates(db) == []
    finally:
        db.close()


def test_transfer_api_exposes_structured_auto_confirmation_evidence():
    db, _, _ = _seed()
    try:
        transfer_detector.detect_candidates(db)
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/transfers", headers=AUTH_HEADERS)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["confirmed"] is True
    assert item["detected_by"] == "auto_confirmed"
    assert item["decision_evidence"]["kind"] == "two_sided_structured"
