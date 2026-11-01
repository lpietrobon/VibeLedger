"""Independent adversarial checks for the PI-04 duplicate implementation.

PI-15 is the immutable contract.  These checks exercise lifecycle and detector
edges that are easy to miss while making that contract pass.
"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Transaction, TransactionAnnotation
from app.services.duplicate_corrections import active_duplicate_ids
from app.services.refund_detector import classify_refunds
from app.services.sync_service import SyncService
from app.services import transfer_detector
from tests.conftest import AUTH_HEADERS
from tests.duplicate_correction_fixture import seed_duplicate_correction_ledger


DUPLICATE_PATH = "/duplicate-corrections"


def _create(client, seeded):
    return client.post(
        DUPLICATE_PATH,
        json={
            "canonical_transaction_id": seeded["transaction_ids"]["market-a"],
            "duplicate_transaction_id": seeded["transaction_ids"]["market-b"],
        },
        headers=AUTH_HEADERS,
    )


def test_provider_currency_conflict_is_not_eligible_for_correction():
    seeded = seed_duplicate_correction_ledger()
    with SessionLocal() as db:
        duplicate = db.get(Transaction, seeded["transaction_ids"]["market-b"])
        duplicate.raw_json = '{"iso_currency_code":"EUR"}'
        db.commit()

    with TestClient(app) as client:
        response = _create(client, seeded)
        assert response.status_code == 400
        assert client.get(DUPLICATE_PATH, headers=AUTH_HEADERS).json()["items"] == []


class _CurrencyModificationClient:
    def get_accounts(self, _access_token):
        return [{
            "account_id": "pi15-fixture-checking", "name": "Checking", "official_name": None,
            "mask": "1234", "type": "depository", "subtype": "checking",
            "current_balance": 1000.0, "available_balance": 1000.0, "iso_currency_code": "EUR", "limit": None,
        }]

    def sync_transactions(self, _access_token, _cursor):
        return {"added": [], "modified": [], "removed": [], "next_cursor": "currency-1"}


def test_account_currency_change_invalidates_active_correction():
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        assert _create(client, seeded).status_code == 200

    with SessionLocal() as db:
        SyncService(client=_CurrencyModificationClient()).sync_item(db, seeded["item_id"])

    with TestClient(app) as client:
        history = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS).json()["items"]
        assert len(history) == 1
        assert history[0]["status"] == "invalidated"


class _ProviderCurrencyModificationClient:
    def get_accounts(self, _access_token):
        return [{
            "account_id": "pi15-fixture-checking", "name": "Checking", "official_name": None,
            "mask": "1234", "type": "depository", "subtype": "checking",
            "current_balance": 1000.0, "available_balance": 1000.0, "iso_currency_code": "USD", "limit": None,
        }]

    def sync_transactions(self, _access_token, _cursor):
        return {
            "added": [],
            "modified": [{
                "transaction_id": "pi15-market-b", "account_id": "pi15-fixture-checking",
                "date": "2026-03-02", "amount": 25.0, "name": "Market", "merchant_name": "Market",
                "plaid_category_primary": "SHOPPING", "pending": False,
                "iso_currency_code": "EUR",
            }],
            "removed": [], "next_cursor": "provider-currency-1",
        }


def test_provider_currency_change_invalidates_active_correction():
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        assert _create(client, seeded).status_code == 200

    with SessionLocal() as db:
        SyncService(client=_ProviderCurrencyModificationClient()).sync_item(db, seeded["item_id"])

    with TestClient(app) as client:
        history = client.get(DUPLICATE_PATH, headers=AUTH_HEADERS).json()["items"]
        assert history[0]["status"] == "invalidated"


def test_active_duplicate_is_not_reused_by_transfer_or_refund_detection():
    seeded = seed_duplicate_correction_ledger()
    with TestClient(app) as client:
        assert _create(client, seeded).status_code == 200

    with SessionLocal() as db:
        item = db.get(Account, seeded["account_id"]).item_id
        other = Account(
            plaid_account_id="pi16-other-account", item_id=item, name="Savings",
            type="depository", subtype="savings", currency="USD",
        )
        db.add(other)
        db.flush()
        incoming = Transaction(
            plaid_transaction_id="pi16-incoming", account_id=other.id, item_id=item,
            date=date(2026, 3, 3), amount=Decimal("-25.00"), name="Market", pending=False,
        )
        refund = Transaction(
            plaid_transaction_id="pi16-refund", account_id=seeded["account_id"], item_id=item,
            date=date(2026, 3, 5), amount=Decimal("-25.00"), name="Market", pending=False,
        )
        db.add_all([incoming, refund])
        db.commit()

        assert seeded["transaction_ids"]["market-b"] in active_duplicate_ids(db)
        created = transfer_detector.detect_candidates(db)
        assert all(
            pair.txn_out_id != seeded["transaction_ids"]["market-b"]
            and pair.txn_in_id != seeded["transaction_ids"]["market-b"]
            for pair in created
        )

        classify_refunds(db)
        refund_annotation = db.query(TransactionAnnotation).filter(
            TransactionAnnotation.transaction_id == refund.id
        ).one()
        assert refund_annotation.refund_match_transaction_id == seeded["transaction_ids"]["market-a"]
