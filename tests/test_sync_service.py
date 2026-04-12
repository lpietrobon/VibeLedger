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
