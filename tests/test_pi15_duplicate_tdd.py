"""PI-15 immutable red tests for manual duplicate correction.

These tests intentionally name the small API contract PI-04 must implement.
Expected accounting values come from ``duplicate_correction_fixture`` and are
never obtained by calling the reporting code under test.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction, TransactionAnnotation, TransferPair
from app.services.security import encrypt_token
from app.services.sync_service import SyncService
from tests.conftest import AUTH_HEADERS
from tests.duplicate_correction_fixture import seed_duplicate_correction_ledger


DUPLICATE_PATH = "/duplicate-corrections"


def _create(client, seeded, *, canonical="market-a", duplicate="market-b"):
    return client.post(
        DUPLICATE_PATH,
        json={
            "canonical_transaction_id": seeded["transaction_ids"][canonical],
            "duplicate_transaction_id": seeded["transaction_ids"][duplicate],
        },
        headers=AUTH_HEADERS,
    )


def _reporting(client):
    bounds = {"start_date": "2026-03-01", "end_date": "2026-03-31"}
    trend = client.get("/analytics/cashflow-trend", params=bounds, headers=AUTH_HEADERS).json()
    monthly = client.get("/analytics/monthly-spend", params=bounds, headers=AUTH_HEADERS).json()
    categories = client.get("/analytics/category-spend", params=bounds, headers=AUTH_HEADERS).json()
    sankey = client.get("/analytics/cashflow-sankey", params=bounds, headers=AUTH_HEADERS).json()
    return {
        "trend": trend[0],
        "monthly": monthly,
        "categories": {row["category"]: row["spend"] for row in categories},
        "sankey": sankey,
    }


def test_duplicate_correction_excludes_only_duplicate_from_all_financial_evidence():
    """PI-03's 100/74/26 -> 100/49/51 hand calculation."""
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        before = _reporting(client)
        assert (before["trend"]["income"], before["trend"]["expenses"], before["trend"]["net"]) == (100.0, 74.0, 26.0)
        assert before["monthly"] == [{"month": "2026-03", "spend": 74.0}]
        assert before["categories"] == {"FOOD": 14.0, "SHOPPING": 60.0, "INCOME": 0.0}

        created = _create(client, seeded)
        assert created.status_code == 200
        body = created.json()
        assert body["status"] == "active"
        correction_id = body["id"]
        assert body["canonical_transaction_id"] == seeded["transaction_ids"]["market-a"]
        assert body["duplicate_transaction_id"] == seeded["transaction_ids"]["market-b"]

        after = _reporting(client)
        assert (after["trend"]["income"], after["trend"]["expenses"], after["trend"]["net"]) == (100.0, 49.0, 51.0)
        assert after["monthly"] == [{"month": "2026-03", "spend": 49.0}]
        assert after["categories"] == {"FOOD": 14.0, "SHOPPING": 35.0, "INCOME": 0.0}
        assert after["sankey"]["total_spend"] == 49.0
        assert sum(bucket["amount"] for bucket in after["sankey"]["buckets"]) == 49.0

        spend = client.get(
            "/transactions",
            params={"start_date": "2026-03-01", "end_date": "2026-03-31", "q": "is:spend", "limit": 100},
            headers=AUTH_HEADERS,
        ).json()
        assert {row["plaid_transaction_id"] for row in spend["items"]} == {
            f"pi15-{key}" for key in seeded["oracle"]["after_spend_ids"]
        }
        assert all(row["plaid_transaction_id"] != "pi15-market-b" for row in spend["items"])

        # Ordinary Activity/search remains source evidence, with relationship labels.
        activity = client.get(
            "/transactions", params={"q": "Market", "limit": 100}, headers=AUTH_HEADERS
        ).json()
        assert {row["plaid_transaction_id"] for row in activity["items"]} == {"pi15-market-a", "pi15-market-b"}
        labels = {row["plaid_transaction_id"]: row["duplicate_status"] for row in activity["items"]}
        assert labels == {"pi15-market-a": "canonical", "pi15-market-b": "duplicate"}

        listed = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS)
        assert listed.status_code == 200
        assert listed.json()["items"] == [body]
        assert correction_id == listed.json()["items"][0]["id"]


def test_active_correction_removes_duplicate_from_recurring_input_only():
    seeded = seed_duplicate_correction_ledger()
    with SessionLocal() as db:
        for key, txn_date in (
            ("sub-jan", date(2026, 1, 12)),
            ("sub-feb-a", date(2026, 2, 12)),
            ("sub-feb-b", date(2026, 2, 12)),
            ("sub-mar", date(2026, 3, 12)),
        ):
            db.add(Transaction(
                plaid_transaction_id=f"pi15-{key}", account_id=seeded["account_id"], item_id=seeded["item_id"],
                date=txn_date, amount=Decimal("15.99"), name="Streamflix",
                merchant_name="Streamflix", plaid_category_primary="ENTERTAINMENT", pending=False,
            ))
        db.commit()
        subscription_ids = {
            tx.plaid_transaction_id: tx.id
            for tx in db.query(Transaction).filter(Transaction.plaid_transaction_id.like("pi15-sub-%"))
        }

    with TestClient(app) as client:
        before = client.get(
            "/analytics/recurring", params={"end_date": "2026-06-30"}, headers=AUTH_HEADERS
        ).json()
        series = next(item for item in before["items"] if item["merchant_label"] == "Streamflix")
        assert series["occurrences"] == 4

        created = client.post(
            DUPLICATE_PATH,
            json={
                "canonical_transaction_id": subscription_ids["pi15-sub-feb-a"],
                "duplicate_transaction_id": subscription_ids["pi15-sub-feb-b"],
            },
            headers=AUTH_HEADERS,
        )
        assert created.status_code == 200

        after = client.get(
            "/analytics/recurring", params={"end_date": "2026-06-30"}, headers=AUTH_HEADERS
        ).json()
        series = next(item for item in after["items"] if item["merchant_label"] == "Streamflix")
        assert series["occurrences"] == 3
        assert series["average_amount"] == 15.99


def test_reversal_restores_accounting_and_releases_both_rows():
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        created = _create(client, seeded)
        assert created.status_code == 200
        correction_id = created.json()["id"]
        reversed_response = client.delete(
            f"{DUPLICATE_PATH}/{correction_id}", headers=AUTH_HEADERS
        )
        assert reversed_response.status_code == 200
        assert reversed_response.json() == {"id": correction_id, "status": "reversed"}

        restored = _reporting(client)
        assert (restored["trend"]["income"], restored["trend"]["expenses"], restored["trend"]["net"]) == (100.0, 74.0, 26.0)
        spend = client.get(
            "/transactions", params={"q": "is:spend", "limit": 100}, headers=AUTH_HEADERS
        ).json()
        assert {row["plaid_transaction_id"] for row in spend["items"]} == {
            f"pi15-{key}" for key in seeded["oracle"]["before_spend_ids"]
        }

        # The relationship is historical, not deleted, and either row is eligible again.
        history = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS).json()["items"]
        assert len(history) == 1
        assert history[0]["status"] == "reversed"


@pytest.mark.parametrize("mutation", ["same", "pending", "different_account", "amount", "currency", "transfer", "refund"])
def test_duplicate_creation_rejects_ineligible_pair_without_partial_relationship(mutation):
    seeded = seed_duplicate_correction_ledger()
    with SessionLocal() as db:
        market_a = db.get(Transaction, seeded["transaction_ids"]["market-a"])
        market_b = db.get(Transaction, seeded["transaction_ids"]["market-b"])
        if mutation == "pending":
            market_b.pending = True
        elif mutation == "different_account":
            account = Account(
                plaid_account_id="pi15-other-account", item_id=market_b.item_id,
                name="Other", type="depository", subtype="checking", currency="USD",
            )
            db.add(account)
            db.flush()
            market_b.account_id = account.id
        elif mutation == "amount":
            market_b.amount = Decimal("24.99")
        elif mutation == "currency":
            db.get(Account, market_b.account_id).currency = "EUR"
        elif mutation == "transfer":
            other = Account(
                plaid_account_id="pi15-transfer-account", item_id=market_a.item_id,
                name="Savings", type="depository", subtype="savings", currency="USD",
            )
            db.add(other)
            db.flush()
            incoming = Transaction(
                plaid_transaction_id="pi15-transfer-in", account_id=other.id, item_id=market_a.item_id,
                date=market_a.date, amount=Decimal("-25.00"), name="Transfer", pending=False,
            )
            db.add(incoming)
            db.flush()
            db.add(TransferPair(txn_out_id=market_a.id, txn_in_id=incoming.id, confirmed=False))
        elif mutation == "refund":
            refund_a = Transaction(
                plaid_transaction_id="pi15-refund-a", account_id=market_a.account_id, item_id=market_a.item_id,
                date=market_a.date, amount=Decimal("-5.00"), name="Refund", pending=False,
            )
            refund_b = Transaction(
                plaid_transaction_id="pi15-refund-b", account_id=market_a.account_id, item_id=market_a.item_id,
                date=market_a.date, amount=Decimal("-5.00"), name="Refund", pending=False,
            )
            db.add_all([refund_a, refund_b])
            db.flush()
            db.add(TransactionAnnotation(transaction_id=refund_a.id, refund_status="likely"))
            market_a, market_b = refund_a, refund_b
        db.commit()
        first_id = market_a.id
        second_id = market_b.id

    with TestClient(app) as client:
        if mutation == "same":
            second_id = first_id
        response = client.post(
            DUPLICATE_PATH,
            json={"canonical_transaction_id": first_id, "duplicate_transaction_id": second_id},
            headers=AUTH_HEADERS,
        )
        assert response.status_code == 400
        assert client.get(DUPLICATE_PATH, headers=AUTH_HEADERS).json()["items"] == []


def test_two_identical_looking_legitimate_charges_remain_counted_without_explicit_action():
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        report = _reporting(client)
        assert report["monthly"] == [{"month": "2026-03", "spend": 74.0}]
        activity = client.get(
            "/transactions", params={"q": "Cafe", "limit": 100}, headers=AUTH_HEADERS
        ).json()
        assert {row["plaid_transaction_id"] for row in activity["items"]} == {"pi15-coffee-a", "pi15-coffee-b"}


def test_active_correction_rejects_overlapping_or_reused_endpoint():
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        created = _create(client, seeded)
        assert created.status_code == 200

        for canonical, duplicate in (("market-a", "book"), ("book", "market-b")):
            response = _create(client, seeded, canonical=canonical, duplicate=duplicate)
            assert response.status_code == 400

        history = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS).json()["items"]
        assert len(history) == 1


def test_provider_replay_does_not_change_active_correction_or_add_a_row():
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        created = _create(client, seeded)
        assert created.status_code == 200

    class ReplayClient:
        def get_accounts(self, _access_token):
            return [{
                "account_id": "pi15-fixture-checking", "name": "Checking", "official_name": None,
                "mask": "1234", "type": "depository", "subtype": "checking",
                "current_balance": 1000.0, "available_balance": 1000.0, "iso_currency_code": "USD", "limit": None,
            }]

        def sync_transactions(self, _access_token, _cursor):
            return {
                "added": [{
                    "transaction_id": "pi15-market-a", "account_id": "pi15-fixture-checking",
                    "date": "2026-03-02", "amount": 25.0, "name": "Market", "merchant_name": "Market",
                    "plaid_category_primary": "SHOPPING", "pending": False,
                }],
                "modified": [], "removed": [], "next_cursor": "replay-1",
            }

    with SessionLocal() as db:
        SyncService(client=ReplayClient()).sync_item(db, seeded["item_id"])
        assert db.query(Transaction).filter(Transaction.plaid_transaction_id == "pi15-market-a").count() == 1

    with TestClient(app) as client:
        history = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS).json()["items"]
        assert len(history) == 1
        assert history[0]["status"] == "active"


def test_material_provider_change_invalidates_correction_and_restores_duplicate_accounting():
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        created = _create(client, seeded)
        assert created.status_code == 200

    class ModificationClient:
        def get_accounts(self, _access_token):
            return [{
                "account_id": "pi15-fixture-checking", "name": "Checking", "official_name": None,
                "mask": "1234", "type": "depository", "subtype": "checking",
                "current_balance": 1000.0, "available_balance": 1000.0, "iso_currency_code": "USD", "limit": None,
            }]

        def sync_transactions(self, _access_token, _cursor):
            return {
                "added": [], "modified": [{
                    "transaction_id": "pi15-market-b", "account_id": "pi15-fixture-checking",
                    "date": "2026-03-02", "amount": 30.0, "name": "Market", "merchant_name": "Market",
                    "plaid_category_primary": "SHOPPING", "pending": False,
                }], "removed": [], "next_cursor": "modified-1",
            }

    with SessionLocal() as db:
        SyncService(client=ModificationClient()).sync_item(db, seeded["item_id"])

    with TestClient(app) as client:
        history = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS).json()["items"]
        assert len(history) == 1
        assert history[0]["status"] == "invalidated"
        assert _reporting(client)["trend"]["expenses"] == 79.0


def test_item_removal_invalidates_correction_and_retains_audit_history():
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        created = _create(client, seeded)
        assert created.status_code == 200
        response = client.post(f"/items/{seeded['item_id']}/remove", headers=AUTH_HEADERS)
        assert response.status_code == 200

        history = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS)
        assert history.status_code == 200
        assert len(history.json()["items"]) == 1
        assert history.json()["items"][0]["status"] == "invalidated"


def test_unambiguous_relink_reapplies_correction_using_retained_source_evidence():
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        created = _create(client, seeded)
        assert created.status_code == 200
        assert client.post(f"/items/{seeded['item_id']}/remove", headers=AUTH_HEADERS).status_code == 200

    with SessionLocal() as db:
        replacement = Item(
            plaid_item_id="pi15-fixture-item",
            access_token_encrypted=encrypt_token("pi15-relinked-token"),
            status="active",
        )
        db.add(replacement)
        db.flush()
        db.add(Account(
            plaid_account_id="pi15-fixture-checking", item_id=replacement.id,
            name="Checking", type="depository", subtype="checking", currency="USD", mask="1234",
        ))
        db.commit()
        replacement_id = replacement.id

    class RelinkClient:
        def get_accounts(self, _access_token):
            return [{
                "account_id": "pi15-fixture-checking", "name": "Checking", "official_name": None,
                "mask": "1234", "type": "depository", "subtype": "checking",
                "current_balance": 1000.0, "available_balance": 1000.0, "iso_currency_code": "USD", "limit": None,
            }]

        def get_historical_transactions(self, _access_token, _start_date, _end_date):
            return [
                {
                    "transaction_id": "pi15-market-a", "account_id": "pi15-fixture-checking",
                    "date": "2026-03-02", "amount": 25.0, "name": "Market", "merchant_name": "Market",
                    "plaid_category_primary": "SHOPPING", "pending": False,
                },
                {
                    "transaction_id": "pi15-market-b", "account_id": "pi15-fixture-checking",
                    "date": "2026-03-02", "amount": 25.0, "name": "Market", "merchant_name": "Market",
                    "plaid_category_primary": "SHOPPING", "pending": False,
                },
            ]

    with SessionLocal() as db:
        SyncService(client=RelinkClient()).sync_item_historical(
            db, replacement_id, date(2026, 3, 1), date(2026, 3, 31)
        )

    with TestClient(app) as client:
        history = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS).json()["items"]
        assert len(history) == 1
        assert history[0]["status"] == "active"


def test_startup_orphan_cleanup_invalidates_missing_endpoint_history():
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        created = _create(client, seeded)
        assert created.status_code == 200
        correction_id = created.json()["id"]

    duplicate_id = seeded["transaction_ids"]["market-b"]
    with SessionLocal() as db:
        db.execute(text("DELETE FROM transactions WHERE id = :id"), {"id": duplicate_id})
        db.commit()

    # Opening the app applies idempotent startup patches and must invalidate an
    # active relationship that now points at a missing source row.
    with TestClient(app) as client:
        history = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS).json()["items"]
        assert history == [{
            "id": correction_id,
            "canonical_transaction_id": seeded["transaction_ids"]["market-a"],
            "duplicate_transaction_id": duplicate_id,
            "status": "invalidated",
        }]


def test_duplicate_schema_and_history_are_idempotent_across_startup():
    with TestClient(app) as client:
        first = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS)
        assert first.status_code == 200
        first_body = first.json()

    with TestClient(app) as client:
        second = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS)
        assert second.status_code == 200
        assert second.json() == first_body == {"items": []}
