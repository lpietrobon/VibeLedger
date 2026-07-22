from datetime import date
import json

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction, TransactionAnnotation
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def _seed_transaction(
    item_plaid_id: str,
    account_plaid_id: str,
    tx_plaid_id: str,
    tx_date: date,
    amount: float,
    name: str,
    plaid_category: str | None = None,
    merchant_name: str | None = None,
    raw_json: str | None = None,
):
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
            merchant_name=merchant_name,
            plaid_category_primary=plaid_category,
            raw_json=raw_json,
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
        assert body["items"][0]["annotation"] == {"user_category": "food", "merchant_name_override": None, "notes": "team lunch", "reviewed": True}

        by_category = client.get("/transactions", params={"category": "food"}, headers=AUTH_HEADERS)
        assert by_category.status_code == 200
        assert [r["plaid_transaction_id"] for r in by_category.json()["items"]] == ["tx-food"]


def test_transaction_filter_matches_unannotated_plaid_category():
    _seed_transaction("i-un", "a-un", "tx-untagged", date(2026, 4, 5), 30.0, "Uber", plaid_category="TRANSPORTATION")

    with TestClient(app) as client:
        # Plaid TRANSPORTATION surfaces under its friendly category name.
        r = client.get("/transactions", params={"category": "TRANSPORT/OTHER"}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert [row["plaid_transaction_id"] for row in r.json()["items"]] == ["tx-untagged"]


def test_user_category_override_can_be_cleared_with_null_or_empty_string():
    tx_id = _seed_transaction(
        "item-clear-cat",
        "acct-clear-cat",
        "tx-clear-cat",
        date(2026, 4, 7),
        22.0,
        "Corner Market",
        plaid_category="GENERAL_MERCHANDISE",
    )

    with TestClient(app) as client:
        set_resp = client.patch(
            f"/transactions/{tx_id}/annotation",
            json={"user_category": "FOOD/GROCERIES"},
            headers=AUTH_HEADERS,
        )
        assert set_resp.status_code == 200

        cleared_null = client.patch(
            f"/transactions/{tx_id}/annotation",
            json={"user_category": None},
            headers=AUTH_HEADERS,
        )
        assert cleared_null.status_code == 200

        row = client.get(
            "/transactions",
            params={"start_date": "2026-04-07", "end_date": "2026-04-07"},
            headers=AUTH_HEADERS,
        ).json()["items"][0]
        assert row["annotation"]["user_category"] is None
        assert row["effective_category"] == "SHOPPING/GENERAL"
        assert row["category_source"] == "plaid"

        reset_resp = client.patch(
            f"/transactions/{tx_id}/annotation",
            json={"user_category": "FOOD/DINING"},
            headers=AUTH_HEADERS,
        )
        assert reset_resp.status_code == 200

        cleared_empty = client.patch(
            f"/transactions/{tx_id}/annotation",
            json={"user_category": ""},
            headers=AUTH_HEADERS,
        )
        assert cleared_empty.status_code == 200

        row = client.get(
            "/transactions",
            params={"start_date": "2026-04-07", "end_date": "2026-04-07"},
            headers=AUTH_HEADERS,
        ).json()["items"][0]
        assert row["annotation"]["user_category"] is None
        assert row["effective_category"] == "SHOPPING/GENERAL"
        assert row["category_source"] == "plaid"


def test_batch_annotation_patch_only_updates_fields_present_in_payload():
    tx_a = _seed_transaction(
        "item-batch-a",
        "acct-batch-a",
        "tx-batch-a",
        date(2026, 4, 9),
        31.0,
        "Batch A",
        plaid_category="DINING",
    )
    tx_b = _seed_transaction(
        "item-batch-b",
        "acct-batch-b",
        "tx-batch-b",
        date(2026, 4, 9),
        42.0,
        "Batch B",
        plaid_category="GENERAL_MERCHANDISE",
    )

    with TestClient(app) as client:
        seed_a = client.patch(
            f"/transactions/{tx_a}/annotation",
            json={"notes": "keep a", "merchant_name_override": "Merchant A"},
            headers=AUTH_HEADERS,
        )
        seed_b = client.patch(
            f"/transactions/{tx_b}/annotation",
            json={"notes": "keep b", "merchant_name_override": "Merchant B"},
            headers=AUTH_HEADERS,
        )
        assert seed_a.status_code == 200
        assert seed_b.status_code == 200

        batch = client.patch(
            "/transactions/annotations/batch",
            json={"transaction_ids": [tx_a, tx_b], "user_category": "BUSINESS/TOOLS", "reviewed": True},
            headers=AUTH_HEADERS,
        )
        assert batch.status_code == 200
        assert batch.json()["updated"] == 2

        rows = client.get(
            "/transactions",
            params={"start_date": "2026-04-09", "end_date": "2026-04-09"},
            headers=AUTH_HEADERS,
        ).json()["items"]

    by_id = {row["id"]: row for row in rows}
    assert by_id[tx_a]["annotation"]["user_category"] == "BUSINESS/TOOLS"
    assert by_id[tx_a]["annotation"]["reviewed"] is True
    assert by_id[tx_a]["annotation"]["notes"] == "keep a"
    assert by_id[tx_a]["annotation"]["merchant_name_override"] == "Merchant A"
    assert by_id[tx_b]["annotation"]["user_category"] == "BUSINESS/TOOLS"
    assert by_id[tx_b]["annotation"]["reviewed"] is True
    assert by_id[tx_b]["annotation"]["notes"] == "keep b"
    assert by_id[tx_b]["annotation"]["merchant_name_override"] == "Merchant B"


def test_batch_annotation_patch_rejects_missing_transaction_without_partial_update():
    tx_id = _seed_transaction(
        "item-batch-missing",
        "acct-batch-missing",
        "tx-batch-missing",
        date(2026, 4, 10),
        18.0,
        "Batch Missing",
        plaid_category="DINING",
    )

    with TestClient(app) as client:
        batch = client.patch(
            "/transactions/annotations/batch",
            json={"transaction_ids": [tx_id, 999999], "user_category": "SHOULD/NOT_APPLY"},
            headers=AUTH_HEADERS,
        )
        assert batch.status_code == 404
        assert batch.json()["detail"] == {"missing_transaction_ids": [999999]}

        row = client.get(
            "/transactions",
            params={"start_date": "2026-04-10", "end_date": "2026-04-10"},
            headers=AUTH_HEADERS,
        ).json()["items"][0]

    assert row["annotation"]["user_category"] is None
    assert row["effective_category"] == "DINING"


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


def test_transactions_include_effective_category_source_and_rule_id_contract():
    tx_rule = _seed_transaction("item-cr1", "acct-cr1", "tx-contract-rule", date(2026, 4, 6), 11.0, "Starbucks Kiosk", plaid_category="DINING")
    _seed_transaction("item-cr4", "acct-cr4", "tx-contract-rule-only", date(2026, 4, 6), 14.0, "Starbucks Reserve", plaid_category="DINING")
    _seed_transaction("item-cr2", "acct-cr2", "tx-contract-plaid", date(2026, 4, 6), 8.0, "Unknown Merchant", plaid_category="PLAID_ONLY")
    _seed_transaction("item-cr3", "acct-cr3", "tx-contract-none", date(2026, 4, 6), 7.0, "No Category", plaid_category=None)

    with TestClient(app) as client:
        create_rule = client.post(
            "/category-rules",
            json={"rank": 1, "enabled": True, "description_regex": "starbucks", "assigned_category": "coffee"},
            headers=AUTH_HEADERS,
        )
        assert create_rule.status_code == 200
        rule_id = create_rule.json()["id"]

        apply_resp = client.post(
            "/category-rules/apply",
            json={"dry_run": False, "scope": {"start_date": "2026-04-01", "end_date": "2026-04-30"}},
            headers=AUTH_HEADERS,
        )
        assert apply_resp.status_code == 200

        client.patch(
            f"/transactions/{tx_rule}/annotation",
            json={"user_category": "manual-coffee"},
            headers=AUTH_HEADERS,
        )

        r = client.get("/transactions", headers=AUTH_HEADERS)
        assert r.status_code == 200

    by_plaid_id = {item["plaid_transaction_id"]: item for item in r.json()["items"]}

    manual_row = by_plaid_id["tx-contract-rule"]
    assert manual_row["effective_category"] == "manual-coffee"
    assert manual_row["category_source"] == "manual"
    assert manual_row["rule_id"] is None

    rule_row = by_plaid_id["tx-contract-rule-only"]
    assert rule_row["effective_category"] == "coffee"
    assert rule_row["category_source"] == "rule"
    assert rule_row["rule_id"] == rule_id

    plaid_row = by_plaid_id["tx-contract-plaid"]
    assert plaid_row["effective_category"] == "PLAID_ONLY"
    assert plaid_row["category_source"] == "plaid"
    assert plaid_row["rule_id"] is None

    uncategorized_row = by_plaid_id["tx-contract-none"]
    assert uncategorized_row["effective_category"] == "uncategorized"
    assert uncategorized_row["category_source"] == "default"
    assert uncategorized_row["rule_id"] is None

    assert rule_id is not None


def test_transactions_include_bank_category_contract_separate_from_effective_category():
    tx_id = _seed_transaction(
        "item-bank-cat",
        "acct-bank-cat",
        "tx-bank-cat",
        date(2026, 4, 8),
        77.0,
        "Sonic Internet",
        plaid_category="RENT_AND_UTILITIES",
        raw_json=json.dumps(
            {
                "personal_finance_category": {
                    "primary": "RENT_AND_UTILITIES",
                    "detailed": "RENT_AND_UTILITIES_INTERNET_AND_CABLE",
                }
            }
        ),
    )

    with TestClient(app) as client:
        client.patch(
            f"/transactions/{tx_id}/annotation",
            json={"user_category": "HOUSING"},
            headers=AUTH_HEADERS,
        )
        r = client.get(
            "/transactions",
            params={"start_date": "2026-04-08", "end_date": "2026-04-08"},
            headers=AUTH_HEADERS,
        )

    assert r.status_code == 200
    row = r.json()["items"][0]
    assert row["plaid_category_primary"] == "RENT_AND_UTILITIES"
    assert row["plaid_category_detailed"] == "RENT_AND_UTILITIES_INTERNET_AND_CABLE"
    assert row["plaid_category_friendly"] == "HOUSING/UTILITIES"
    assert row["effective_category"] == "HOUSING"
    assert row["category_source"] == "manual"


def test_merchant_name_override_patch_and_roundtrip():
    tx_id = _seed_transaction("item-mo1", "acct-mo1", "tx-mo1", date(2026, 5, 1), 42.0, "DUNKIN #123", merchant_name="Dunkin")

    with TestClient(app) as client:
        resp = client.patch(
            f"/transactions/{tx_id}/annotation",
            json={"merchant_name_override": "Dunkin Donuts"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200

        r = client.get("/transactions", params={"start_date": "2026-05-01", "end_date": "2026-05-01"}, headers=AUTH_HEADERS)
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        row = items[0]
        assert row["merchant_name"] == "Dunkin"                             # raw Plaid unchanged
        assert row["annotation"]["merchant_name_override"] == "Dunkin Donuts"


def test_merchant_name_on_transaction_immutable_after_annotation_patch():
    tx_id = _seed_transaction("item-mo2", "acct-mo2", "tx-mo2", date(2026, 5, 2), 15.0, "STARBUCKS", merchant_name="Starbucks")

    with TestClient(app) as client:
        client.patch(
            f"/transactions/{tx_id}/annotation",
            json={"merchant_name_override": "Coffee Shop"},
            headers=AUTH_HEADERS,
        )

    with SessionLocal() as db:
        tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
        assert tx.merchant_name == "Starbucks"


def test_manual_refund_classification_roundtrip():
    tx_id = _seed_transaction(
        "item-refund-manual",
        "acct-refund-manual",
        "tx-refund-manual",
        date(2026, 5, 3),
        -42.0,
        "Merchant credit",
        plaid_category="GENERAL_MERCHANDISE",
    )

    with TestClient(app) as client:
        marked = client.patch(
            f"/transactions/{tx_id}/annotation",
            json={"refund_status": "confirmed"},
            headers=AUTH_HEADERS,
        )
        assert marked.status_code == 200

        row = client.get("/transactions", headers=AUTH_HEADERS).json()["items"][0]
        assert row["refund_status"] == "confirmed"
        assert row["refund_reason"] == "Manual classification"

        automatic = client.patch(
            f"/transactions/{tx_id}/annotation",
            json={"refund_status": "auto"},
            headers=AUTH_HEADERS,
        )
        assert automatic.status_code == 200

        row = client.get("/transactions", headers=AUTH_HEADERS).json()["items"][0]
        assert row["refund_status"] is None


def test_merchant_name_override_clear_with_empty_string():
    tx_id = _seed_transaction("item-mo3", "acct-mo3", "tx-mo3", date(2026, 5, 3), 9.0, "CAFE", merchant_name="Cafe Raw")

    with TestClient(app) as client:
        client.patch(
            f"/transactions/{tx_id}/annotation",
            json={"merchant_name_override": "My Cafe"},
            headers=AUTH_HEADERS,
        )
        # Clear the override with empty string
        client.patch(
            f"/transactions/{tx_id}/annotation",
            json={"merchant_name_override": ""},
            headers=AUTH_HEADERS,
        )
        r = client.get("/transactions", params={"start_date": "2026-05-03", "end_date": "2026-05-03"}, headers=AUTH_HEADERS)
        row = r.json()["items"][0]
        assert row["annotation"]["merchant_name_override"] is None
        assert row["merchant_name"] == "Cafe Raw"   # raw Plaid value still intact


def test_merchant_name_override_absent_when_no_annotation():
    tx_id = _seed_transaction("item-mo4", "acct-mo4", "tx-mo4", date(2026, 5, 4), 7.0, "RAW MERCHANT", merchant_name="Raw Merchant")

    with TestClient(app) as client:
        r = client.get("/transactions", params={"start_date": "2026-05-04", "end_date": "2026-05-04"}, headers=AUTH_HEADERS)

    row = r.json()["items"][0]
    assert row["merchant_name"] == "Raw Merchant"
    assert row["annotation"]["merchant_name_override"] is None
