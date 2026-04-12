from datetime import timedelta

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.models import AccountBalanceSnapshot, Item, SyncRun, SyncState, Transaction
from app.services.security import encrypt_token
from app.services.sync_service import SyncService


class FakePlaidClient:
    def __init__(self):
        self.calls = 0

    def get_accounts(self, _access_token):
        return [
            {
                "account_id": "acct-100",
                "name": "Checking",
                "official_name": "Main Checking",
                "mask": "1234",
                "type": "depository",
                "subtype": "checking",
                "current_balance": 500.0,
                "available_balance": 450.0,
                "iso_currency_code": "USD",
                "limit": None,
            }
        ]

    def sync_transactions(self, _access_token, cursor):
        self.calls += 1
        if cursor is None:
            return {
                "added": [
                    {
                        "transaction_id": "txn-1",
                        "account_id": "acct-100",
                        "date": "2026-04-10",
                        "amount": 20.0,
                        "name": "Lunch",
                        "merchant_name": "Cafe",
                        "plaid_category_primary": "FOOD_AND_DRINK",
                        "pending": False,
                    }
                ],
                "modified": [],
                "removed": [],
                "next_cursor": "cursor-1",
            }

        return {
            "added": [],
            "modified": [
                {
                    "transaction_id": "txn-1",
                    "account_id": "acct-100",
                    "date": "2026-04-10",
                    "amount": 25.0,
                    "name": "Lunch updated",
                    "merchant_name": "Cafe",
                    "plaid_category_primary": "FOOD_AND_DRINK",
                    "pending": True,
                }
            ],
            "removed": [{"transaction_id": "txn-1"}],
            "next_cursor": "cursor-2",
        }


def test_sync_item_tracks_state_and_mutates_transactions():
    client = FakePlaidClient()
    service = SyncService(client=client)

    with SessionLocal() as db:
        item = Item(
            plaid_item_id="item-1",
            access_token_encrypted=encrypt_token("secret-access-token"),
            status="active",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        first = service.sync_item(db, item.id)
        assert first == {"status": "success", "added": 1, "modified": 0, "removed": 0, "cursor": "cursor-1"}

        tx = db.query(Transaction).filter(Transaction.plaid_transaction_id == "txn-1").first()
        assert tx is not None
        assert float(tx.amount) == 20.0

        second = service.sync_item(db, item.id)
        assert second == {"status": "success", "added": 0, "modified": 1, "removed": 1, "cursor": "cursor-2"}

        assert db.query(Transaction).filter(Transaction.plaid_transaction_id == "txn-1").first() is None

        state = db.query(SyncState).filter(SyncState.item_id == item.id).first()
        assert state is not None
        assert state.cursor == "cursor-2"
        assert state.last_success_at is not None

        runs = db.query(SyncRun).filter(SyncRun.item_id == item.id).order_by(SyncRun.id.asc()).all()
        assert [r.status for r in runs] == ["success", "success"]
        assert [(r.added_count, r.modified_count, r.removed_count) for r in runs] == [(1, 0, 0), (0, 1, 1)]


def test_sync_item_missing_item_errors():
    with SessionLocal() as db:
        service = SyncService(client=FakePlaidClient())
        try:
            service.sync_item(db, 9999)
        except ValueError as e:
            assert str(e) == "item not found"
        else:
            raise AssertionError("Expected ValueError for missing item")


def test_sync_replay_idempotent_for_repeated_added():
    class ReplayClient:
        def __init__(self):
            self.call = 0

        def get_accounts(self, _at):
            return [
                {
                    "account_id": "acct-replay",
                    "name": "Checking",
                    "official_name": None,
                    "mask": None,
                    "type": "depository",
                    "subtype": "checking",
                    "current_balance": 100.0,
                    "available_balance": 100.0,
                    "iso_currency_code": "USD",
                    "limit": None,
                }
            ]

        def sync_transactions(self, _at, cursor):
            self.call += 1
            return {
                "added": [
                    {
                        "transaction_id": "txn-replay",
                        "account_id": "acct-replay",
                        "date": "2026-04-05",
                        "amount": 10.0,
                        "name": "Same",
                        "merchant_name": None,
                        "plaid_category_primary": None,
                        "pending": False,
                    }
                ],
                "modified": [],
                "removed": [],
                "next_cursor": f"cursor-{self.call}",
            }

    service = SyncService(client=ReplayClient())
    with SessionLocal() as db:
        item = Item(plaid_item_id="item-replay", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.commit()
        db.refresh(item)

        first = service.sync_item(db, item.id)
        assert first["added"] == 1
        assert first["modified"] == 0

        second = service.sync_item(db, item.id)
        assert second["added"] == 0
        assert second["modified"] == 0

        txn_count = db.query(Transaction).filter(Transaction.plaid_transaction_id == "txn-replay").count()
        assert txn_count == 1


class FailingPlaidClient:
    """PlaidClient that raises on sync_transactions."""

    def __init__(self, fail_on="sync"):
        self.fail_on = fail_on

    def get_accounts(self, _access_token):
        if self.fail_on == "accounts":
            raise RuntimeError("Plaid accounts API unavailable")
        return [
            {
                "account_id": "acct-fail",
                "name": "Checking",
                "official_name": None,
                "mask": None,
                "type": "depository",
                "subtype": "checking",
                "current_balance": 100.0,
                "available_balance": 100.0,
                "iso_currency_code": "USD",
                "limit": None,
            }
        ]

    def sync_transactions(self, _access_token, cursor):
        raise RuntimeError("Plaid sync API unavailable")


def test_sync_item_plaid_failure_sets_error_status():
    service = SyncService(client=FailingPlaidClient())

    with SessionLocal() as db:
        item = Item(plaid_item_id="item-fail", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.commit()
        db.refresh(item)

        try:
            service.sync_item(db, item.id)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected RuntimeError")

        run = db.query(SyncRun).filter(SyncRun.item_id == item.id).first()
        assert run is not None
        assert run.status == "error"
        assert run.finished_at is not None
        assert "RuntimeError" in run.error_summary

        state = db.query(SyncState).filter(SyncState.item_id == item.id).first()
        assert state is not None
        assert state.cursor is None  # cursor not advanced on failure
        assert state.last_error_code == "RuntimeError"
        assert state.consecutive_failures == 1


def test_sync_consecutive_failures_increment():
    service = SyncService(client=FailingPlaidClient())

    with SessionLocal() as db:
        item = Item(plaid_item_id="item-fail2", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.commit()
        db.refresh(item)

        for expected_count in (1, 2):
            try:
                service.sync_item(db, item.id)
            except RuntimeError:
                pass
            state = db.query(SyncState).filter(SyncState.item_id == item.id).first()
            assert state.consecutive_failures == expected_count


def test_sync_success_after_failure_resets_failures():
    fail_client = FailingPlaidClient()
    service = SyncService(client=fail_client)

    with SessionLocal() as db:
        item = Item(plaid_item_id="item-recover", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.commit()
        db.refresh(item)

        try:
            service.sync_item(db, item.id)
        except RuntimeError:
            pass
        state = db.query(SyncState).filter(SyncState.item_id == item.id).first()
        assert state.consecutive_failures == 1

    # Now sync with a working client
    ok_service = SyncService(client=FakePlaidClient())
    with SessionLocal() as db:
        item = db.query(Item).filter(Item.plaid_item_id == "item-recover").first()
        ok_service.sync_item(db, item.id)

        state = db.query(SyncState).filter(SyncState.item_id == item.id).first()
        assert state.consecutive_failures == 0
        assert state.last_error_code is None


def test_stale_run_recovery():
    with SessionLocal() as db:
        item = Item(plaid_item_id="item-stale", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.commit()
        db.refresh(item)

        # Manually insert a stale SyncRun (started 60 minutes ago)
        stale_run = SyncRun(
            item_id=item.id,
            status="running",
            started_at=utcnow() - timedelta(minutes=60),
        )
        db.add(stale_run)
        db.commit()
        stale_run_id = stale_run.id

        # Sync should succeed because the stale run is auto-recovered
        service = SyncService(client=FakePlaidClient())
        result = service.sync_item(db, item.id)
        assert result["status"] == "success"

        # Verify the stale run was marked as error
        recovered = db.query(SyncRun).filter(SyncRun.id == stale_run_id).first()
        assert recovered.status == "error"
        assert "stale" in recovered.error_summary


def test_balance_snapshots_dedup_within_same_day():
    client = FakePlaidClient()
    service = SyncService(client=client)

    with SessionLocal() as db:
        item = Item(plaid_item_id="item-snap", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.commit()
        db.refresh(item)

        service.sync_item(db, item.id)
        service.sync_item(db, item.id)

        snap_count = db.query(AccountBalanceSnapshot).count()
        assert snap_count == 1
