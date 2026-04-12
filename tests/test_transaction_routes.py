from datetime import date

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def _seed_transaction(item_plaid_id: str, account_plaid_id: str, tx_plaid_id: str, tx_date: date, amount: float, name: str, plaid_category: str | None = None):
    with SessionLocal() as db:
        item = Item(plaid_item_id=item_plaid_id, access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.flush()

        account = Account(plaid_account_id=account_plaid_id, item_id=item.id, name="Test Account")
        db.add(account)
        db.flush()

        tx = Transaction(
            plaid_transaction_id=tx_plaid_id,
            account_id=account.id,
            item_id=item.id,
            date=tx_date,
            amount=amount,
            name=name,
            plaid_category_primary=plaid_category,
            pending=False,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx.id


def test_annotation_patch_and_transaction_filters_work_end_to_end():
    tx_food = _seed_transaction("item-f", "acct-f", "tx-food", date(2026, 4, 1), 18.5, "Tacos")
    _seed_transaction("item-r", "acct-r", "tx-rent", date(2026, 3, 20), 1200.0, "Rent")

    with TestClient(app) as client:
        patch_resp = client.patch(
            f"/transactions/{tx_food}/annotation",
            json={"user_category": "food", "notes": "team lunch", "reviewed": 1},
            headers=AUTH_HEADERS,
        )
        assert patch_resp.status_code == 200

        filtered = client.get("/transactions", params={"start_date": "2026-04-01", "end_date": "2026-04-30"}, headers=AUTH_HEADERS)
        assert filtered.status_code == 200
        body = filtered.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["plaid_transaction_id"] == "tx-food"
        assert body["items"][0]["annotation"] == {"user_category": "food", "notes": "team lunch", "reviewed": True}

        by_category = client.get("/transactions", params={"category": "food"}, headers=AUTH_HEADERS)
        assert by_category.status_code == 200
        assert [r["plaid_transaction_id"] for r in by_category.json()["items"]] == ["tx-food"]


def test_transaction_filter_matches_unannotated_plaid_category():
    _seed_transaction("i-un", "a-un", "tx-untagged", date(2026, 4, 5), 30.0, "Uber", plaid_category="TRANSPORTATION")

    with TestClient(app) as client:
        r = client.get("/transactions", params={"category": "TRANSPORTATION"}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert [row["plaid_transaction_id"] for row in r.json()["items"]] == ["tx-untagged"]


def test_transaction_pagination():
    for i in range(5):
        _seed_transaction(f"ip-{i}", f"ap-{i}", f"tx-p{i}", date(2026, 4, 1 + i), 10.0 * (i + 1), f"Tx {i}")

    with TestClient(app) as client:
        r = client.get("/transactions", params={"limit": 2, "offset": 0}, headers=AUTH_HEADERS)
        body = r.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2

        r2 = client.get("/transactions", params={"limit": 2, "offset": 2}, headers=AUTH_HEADERS)
        body2 = r2.json()
        assert body2["total"] == 5
        assert len(body2["items"]) == 2
        assert body["items"][0]["id"] != body2["items"][0]["id"]
