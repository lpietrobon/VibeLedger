from datetime import date

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, CategoryDecisionEvent, Item, Transaction, TransactionAnnotation
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def _seed_tx(item_suffix: str, account_name: str, plaid_txn_id: str, amount: float, name: str, tx_date: date, plaid_category: str = "OTHER"):
    with SessionLocal() as db:
        item = Item(plaid_item_id=f"item-{item_suffix}", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.flush()
        account = Account(plaid_account_id=f"acct-{item_suffix}", item_id=item.id, name=account_name)
        db.add(account)
        db.flush()
        tx = Transaction(
            plaid_transaction_id=plaid_txn_id,
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


def test_category_rule_crud_preview_and_apply():
    tx_match = _seed_tx("rule-1", "Checking", "tx-rule-1", 9.99, "Starbucks #123", date(2026, 4, 1))
    tx_other = _seed_tx("rule-2", "Checking", "tx-rule-2", 23.50, "Grocery Mart", date(2026, 4, 2))

    with TestClient(app) as client:
        create_resp = client.post(
            "/category-rules",
            json={"rank": 1, "enabled": True, "description_regex": "starbucks", "assigned_category": "coffee", "name": "Coffee Rule"},
            headers=AUTH_HEADERS,
        )
        assert create_resp.status_code == 200
        rule_id = create_resp.json()["id"]

        list_resp = client.get("/category-rules", headers=AUTH_HEADERS)
        assert list_resp.status_code == 200
        assert len(list_resp.json()["items"]) == 1

        preview = client.post(
            "/category-rules/preview",
            json={"rule_id": rule_id, "scope": {"start_date": "2026-04-01", "end_date": "2026-04-30"}},
            headers=AUTH_HEADERS,
        )
        assert preview.status_code == 200
        body = preview.json()
        assert body["total_scanned"] == 2
        assert body["would_change_count"] == 1
        assert body["samples"][0]["transaction_id"] == tx_match
        assert body["samples"][0]["simulated_effective_category"] == "coffee"

        dry_run = client.post(
            "/category-rules/apply",
            json={"dry_run": True, "scope": {"start_date": "2026-04-01", "end_date": "2026-04-30"}},
            headers=AUTH_HEADERS,
        )
        assert dry_run.status_code == 200
        assert dry_run.json()["would_change_count"] == 1

        apply_resp = client.post(
            "/category-rules/apply",
            json={"dry_run": False, "scope": {"start_date": "2026-04-01", "end_date": "2026-04-30"}},
            headers=AUTH_HEADERS,
        )
        assert apply_resp.status_code == 200
        assert apply_resp.json()["event_count"] == 1

        with SessionLocal() as db:
            ann_match = db.query(TransactionAnnotation).filter(TransactionAnnotation.transaction_id == tx_match).first()
            ann_other = db.query(TransactionAnnotation).filter(TransactionAnnotation.transaction_id == tx_other).first()
            assert ann_match is not None
            assert ann_match.rule_category == "coffee"
            assert ann_match.rule_id == rule_id
            assert ann_match.rule_evaluated_at is not None
            assert ann_other is not None
            assert ann_other.rule_category is None
            events = db.query(CategoryDecisionEvent).all()
            assert len(events) == 1

        delete_resp = client.delete(f"/category-rules/{rule_id}", headers=AUTH_HEADERS)
        assert delete_resp.status_code == 200


def test_apply_does_not_override_manual_user_category():
    tx_id = _seed_tx("manual", "Card", "tx-manual", 12.00, "Starbucks Reserve", date(2026, 4, 3), "DINING")

    with SessionLocal() as db:
        db.add(TransactionAnnotation(transaction_id=tx_id, user_category="manual_override"))
        db.commit()

    with TestClient(app) as client:
        client.post(
            "/category-rules",
            json={"rank": 1, "enabled": True, "description_regex": "starbucks", "assigned_category": "coffee"},
            headers=AUTH_HEADERS,
        )
        apply_resp = client.post(
            "/category-rules/apply",
            json={"dry_run": False, "scope": {"start_date": "2026-04-01", "end_date": "2026-04-30"}},
            headers=AUTH_HEADERS,
        )
        assert apply_resp.status_code == 200

    with SessionLocal() as db:
        ann = db.query(TransactionAnnotation).filter(TransactionAnnotation.transaction_id == tx_id).first()
        assert ann is not None
        assert ann.user_category == "manual_override"
        assert ann.rule_category is None


def test_recompute_all_endpoint():
    _seed_tx("recompute", "Checking", "tx-recompute", 15.00, "Cafe Latte", date(2026, 4, 4))
    with TestClient(app) as client:
        create_resp = client.post(
            "/category-rules",
            json={"rank": 1, "enabled": True, "description_regex": "cafe", "assigned_category": "coffee"},
            headers=AUTH_HEADERS,
        )
        assert create_resp.status_code == 200

        resp = client.post("/category-rules/recompute-all", json={"batch_size": 50}, headers=AUTH_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["updated_count"] >= 1
