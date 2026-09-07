"""Failed imports retain only error metadata, never a half-applied ledger batch."""
from datetime import date
from decimal import Decimal

import pytest

from app.db.session import SessionLocal
from app.models.models import Account, AccountBalanceSnapshot, Item, SyncRun, SyncState, Transaction
from app.services.security import encrypt_token
from app.services.sync_service import SyncService


class BatchClient:
    def __init__(self):
        self.rows = [self.record("first"), self.record("second", day="invalid-date")]

    @staticmethod
    def record(identifier, day="2026-04-10"):
        return {"transaction_id": identifier, "account_id": "atomic-account",
                "date": day, "amount": 25, "name": "Purchase", "pending": False}

    def get_accounts(self, token):
        return [{"account_id": "atomic-account", "name": "Checking", "mask": "1234",
                 "type": "depository", "subtype": "checking", "current_balance": 500,
                 "available_balance": 500, "iso_currency_code": "USD"}]

    def sync_transactions(self, token, cursor):
        return {"added": self.rows, "next_cursor": "next"}

    def get_historical_transactions(self, token, start_date, end_date):
        return self.rows


@pytest.mark.parametrize("historical", [False, True])
@pytest.mark.parametrize("existing_account", [False, True])
def test_failed_batch_preserves_ledger_balances_cursor_and_can_retry(historical, existing_account):
    client = BatchClient()
    service = SyncService(client)
    with SessionLocal() as db:
        item = Item(plaid_item_id="atomic-item", access_token_encrypted=encrypt_token("synthetic"))
        db.add(item)
        db.flush()
        item_id = item.id
        db.add(SyncState(item_id=item_id, cursor="previous"))
        if existing_account:
            db.add(Account(plaid_account_id="atomic-account", item_id=item_id,
                           name="Old name", current_balance=100, available_balance=90,
                           currency="USD"))
        db.commit()

        def sync():
            if historical:
                return service.sync_item_historical(db, item_id, date(2026, 4, 1), date(2026, 4, 30))
            return service.sync_item(db, item_id)

        with pytest.raises(ValueError):
            sync()

        # Read after expiration so this checks committed DB state, not cached ORM values.
        db.expire_all()
        assert db.query(Transaction).count() == 0
        assert db.query(AccountBalanceSnapshot).count() == 0
        assert db.query(SyncState).one().cursor == "previous"
        assert db.query(Account).count() == int(existing_account)
        if existing_account:
            account = db.query(Account).one()
            assert (account.name, account.current_balance, account.available_balance) == (
                "Old name", Decimal("100"), Decimal("90"))
        failed = db.query(SyncRun).one()
        assert failed.status == "error" and failed.finished_at is not None
        assert "ValueError" in failed.error_summary

        client.rows = [client.record("first"), client.record("second")]
        assert sync()["added"] == 2
        assert db.query(Transaction).count() == 2
        assert db.query(Account).one().current_balance == Decimal("500")
        assert db.query(AccountBalanceSnapshot).count() == 1
        assert db.query(SyncState).one().cursor == ("previous" if historical else "next")
        assert [run.status for run in db.query(SyncRun).order_by(SyncRun.id)] == ["error", "success"]
        assert sync()["added"] == 0
        assert db.query(Transaction).count() == 2
