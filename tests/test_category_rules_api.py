from datetime import date

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, CategoryDecisionEvent, CategoryRule, Item, Transaction, TransactionAnnotation
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


def test_category_rule_crud_validation_behavior_and_delete():
    with TestClient(app) as client:
        invalid_create = client.post(
            "/category-rules",
            json={"rank": 1, "enabled": True, "description_regex": "(", "assigned_category": "coffee"},
            headers=AUTH_HEADERS,
        )
        assert invalid_create.status_code == 400
        assert "invalid regex" in invalid_create.json()["detail"]

        create_resp = client.post(
            "/category-rules",
            json={"rank": 3, "enabled": True, "description_regex": "starbucks", "assigned_category": "coffee", "name": "Coffee Rule"},
            headers=AUTH_HEADERS,
        )
        assert create_resp.status_code == 200
        rule_id = create_resp.json()["id"]

        patch_resp = client.patch(
            f"/category-rules/{rule_id}",
            json={"rank": 2, "description_regex": "cafe", "assigned_category": "coffee-shop"},
            headers=AUTH_HEADERS,
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["rank"] == 2
        assert patch_resp.json()["description_regex"] == "cafe"
        assert patch_resp.json()["assigned_category"] == "coffee-shop"

        missing_patch = client.patch("/category-rules/999999", json={"rank": 1}, headers=AUTH_HEADERS)
        assert missing_patch.status_code == 404

        list_resp = client.get("/category-rules", headers=AUTH_HEADERS)
        assert list_resp.status_code == 200
        assert len(list_resp.json()["items"]) == 1

        delete_resp = client.delete(f"/category-rules/{rule_id}", headers=AUTH_HEADERS)
        assert delete_resp.status_code == 200

        missing_delete = client.delete(f"/category-rules/{rule_id}", headers=AUTH_HEADERS)
        assert missing_delete.status_code == 404


def test_preview_returns_diffs_without_mutating_db_and_dry_run_does_not_persist_changes():
    tx_match = _seed_tx("preview-1", "Checking", "tx-preview-1", 9.99, "Starbucks #123", date(2026, 4, 1), "DINING")
    tx_other = _seed_tx("preview-2", "Checking", "tx-preview-2", 23.50, "Grocery Mart", date(2026, 4, 2), "GROCERIES")

    with TestClient(app) as client:
        create_resp = client.post(
            "/category-rules",
            json={"rank": 1, "enabled": True, "description_regex": "starbucks", "assigned_category": "coffee", "name": "Coffee Rule"},
            headers=AUTH_HEADERS,
        )
        assert create_resp.status_code == 200
        rule_id = create_resp.json()["id"]

        preview = client.post(
            "/category-rules/preview",
            json={"rule_id": rule_id, "scope": {"start_date": "2026-04-01", "end_date": "2026-04-30"}},
            headers=AUTH_HEADERS,
        )
        assert preview.status_code == 200
        body = preview.json()
        assert body["total_scanned"] == 2
        assert body["would_change_count"] == 1
        assert [sample["transaction_id"] for sample in body["samples"]] == [tx_match]
        assert body["samples"][0]["current_effective_category"] == "DINING"
        assert body["samples"][0]["simulated_effective_category"] == "coffee"

        with SessionLocal() as db:
            assert db.query(TransactionAnnotation).count() == 0
            assert db.query(CategoryDecisionEvent).count() == 0

        dry_run = client.post(
            "/category-rules/apply",
            json={"dry_run": True, "scope": {"start_date": "2026-04-01", "end_date": "2026-04-30"}},
            headers=AUTH_HEADERS,
        )
        assert dry_run.status_code == 200
        assert dry_run.json()["would_change_count"] == 1
        assert dry_run.json()["updated_count"] == 0
        assert dry_run.json()["event_count"] == 0

    with SessionLocal() as db:
        assert db.query(TransactionAnnotation).count() == 0
        assert db.query(CategoryDecisionEvent).count() == 0
        assert db.query(Transaction).filter(Transaction.id == tx_other).first() is not None


def test_apply_persists_rule_annotation_and_audit_events_and_never_overrides_user_category():
    tx_rule = _seed_tx("apply-1", "Card", "tx-apply-1", 12.00, "Starbucks Reserve", date(2026, 4, 3), "DINING")
    tx_manual = _seed_tx("apply-2", "Card", "tx-apply-2", 13.00, "Starbucks Roastery", date(2026, 4, 4), "DINING")

    with SessionLocal() as db:
        db.add(TransactionAnnotation(transaction_id=tx_manual, user_category="manual_override"))
        db.commit()

    with TestClient(app) as client:
        create_resp = client.post(
            "/category-rules",
            json={"rank": 1, "enabled": True, "description_regex": "starbucks", "assigned_category": "coffee"},
            headers=AUTH_HEADERS,
        )
        assert create_resp.status_code == 200
        rule_id = create_resp.json()["id"]

        apply_resp = client.post(
            "/category-rules/apply",
            json={"dry_run": False, "scope": {"start_date": "2026-04-01", "end_date": "2026-04-30"}},
            headers=AUTH_HEADERS,
        )
        assert apply_resp.status_code == 200
        payload = apply_resp.json()
        assert payload["event_count"] == 1
        assert payload["updated_count"] == 1
        assert payload["run_summary"]["skipped_manual"] == 1

    with SessionLocal() as db:
        ann_rule = db.query(TransactionAnnotation).filter(TransactionAnnotation.transaction_id == tx_rule).first()
        ann_manual = db.query(TransactionAnnotation).filter(TransactionAnnotation.transaction_id == tx_manual).first()
        assert ann_rule is not None
        assert ann_rule.rule_category == "coffee"
        assert ann_rule.rule_id == rule_id
        assert ann_rule.rule_evaluated_at is not None

        assert ann_manual is not None
        assert ann_manual.user_category == "manual_override"
        assert ann_manual.rule_category is None
        assert ann_manual.rule_id is None

        events = db.query(CategoryDecisionEvent).order_by(CategoryDecisionEvent.id.asc()).all()
        assert len(events) == 1
        assert events[0].transaction_id == tx_rule
        assert events[0].rule_id == rule_id
        assert events[0].source == "rule_apply"


def test_apply_batch_performance_sanity_on_fixture_dataset():
    with SessionLocal() as db:
        item = Item(plaid_item_id="item-batch", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.flush()
        account = Account(plaid_account_id="acct-batch", item_id=item.id, name="Batch Card")
        db.add(account)
        db.flush()

        rows = []
        for i in range(600):
            is_match = i % 2 == 0
            name = f"Starbucks #{i}" if is_match else f"Other Merchant #{i}"
            rows.append(
                Transaction(
                    plaid_transaction_id=f"tx-batch-{i}",
                    account_id=account.id,
                    item_id=item.id,
                    date=date(2026, 4, (i % 28) + 1),
                    amount=10 + (i % 20),
                    name=name,
                    plaid_category_primary="PLAID_MISC",
                    pending=False,
                )
            )
        db.add_all(rows)
        db.commit()

    with TestClient(app) as client:
        create_resp = client.post(
            "/category-rules",
            json={"rank": 1, "enabled": True, "description_regex": "starbucks", "assigned_category": "coffee"},
            headers=AUTH_HEADERS,
        )
        assert create_resp.status_code == 200

        apply_resp = client.post(
            "/category-rules/apply",
            json={
                "dry_run": False,
                "batch_size": 200,
                "scope": {"start_date": "2026-04-01", "end_date": "2026-04-30"},
            },
            headers=AUTH_HEADERS,
        )
        assert apply_resp.status_code == 200
        payload = apply_resp.json()

    assert payload["total_scanned"] == 600
    assert payload["updated_count"] == 600
    assert payload["event_count"] == 300
    assert payload["would_change_count"] == 300
    assert payload["run_summary"]["duration_ms"] < 3000


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

        with SessionLocal() as db:
            assert db.query(CategoryRule).count() == 1
