from datetime import date

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction
from app.services.security import encrypt_token


def _seed_transaction(item_plaid_id: str, account_plaid_id: str, tx_plaid_id: str, tx_date: date, amount: float, name: str):
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
        )
        assert patch_resp.status_code == 200

        filtered = client.get("/transactions", params={"start_date": "2026-04-01", "end_date": "2026-04-30"})
        assert filtered.status_code == 200
        rows = filtered.json()
        assert len(rows) == 1
        assert rows[0]["plaid_transaction_id"] == "tx-food"
        assert rows[0]["annotation"] == {"user_category": "food", "notes": "team lunch", "reviewed": True}

        by_category = client.get("/transactions", params={"category": "food"})
        assert by_category.status_code == 200
        assert [r["plaid_transaction_id"] for r in by_category.json()] == ["tx-food"]
