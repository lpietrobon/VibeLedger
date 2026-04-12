import json
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.models import Account, AccountBalanceSnapshot, Item, SyncRun, SyncState, Transaction
from app.services.plaid_client import PlaidClient
from app.services.security import decrypt_token

logger = logging.getLogger(__name__)


class SyncInProgressError(Exception):
    pass


class SyncService:
    def __init__(self, client: PlaidClient | None = None):
        self.client = client or PlaidClient()

    def sync_item(self, db: Session, item_id: int) -> dict:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError("item not found")

        # Recover stale runs (stuck > 30 minutes)
        stale_cutoff = utcnow() - timedelta(minutes=30)
        stale_runs = (
            db.query(SyncRun)
            .filter(SyncRun.item_id == item_id, SyncRun.status == "running", SyncRun.started_at < stale_cutoff)
            .all()
        )
        for stale in stale_runs:
            stale.status = "error"
            stale.finished_at = utcnow()
            stale.error_summary = "marked stale: exceeded 30-minute timeout"
            logger.warning("Marked stale SyncRun %d for item %d", stale.id, item_id)
        if stale_runs:
            db.flush()

        in_progress = (
            db.query(SyncRun)
            .filter(SyncRun.item_id == item_id, SyncRun.status == "running")
            .first()
        )
        if in_progress:
            raise SyncInProgressError("sync already running for this item")

        state = db.query(SyncState).filter(SyncState.item_id == item_id).first()
        if not state:
            state = SyncState(item_id=item_id, cursor=None)
            db.add(state)
            db.flush()

        run = SyncRun(item_id=item_id, status="running")
        db.add(run)
        db.flush()

        try:
            access_token = decrypt_token(item.access_token_encrypted)
            self._refresh_accounts_and_snapshots(db, item_id, access_token)
            data = self.client.sync_transactions(access_token, state.cursor)
            added_count, modified_count, removed_count = self._apply_changes(db, item_id, data)
        except Exception as exc:
            now = utcnow()
            run.status = "error"
            run.finished_at = now
            run.error_summary = f"{type(exc).__name__}: {exc}"[:500]

            state.last_sync_at = now
            state.last_error_code = type(exc).__name__
            state.last_error_message = str(exc)[:1000]
            state.consecutive_failures = (state.consecutive_failures or 0) + 1

            db.commit()
            raise

        now = utcnow()
        state.cursor = data.get("next_cursor")
        state.last_sync_at = now
        state.last_success_at = now
        state.last_error_code = None
        state.last_error_message = None
        state.consecutive_failures = 0

        run.status = "success"
        run.added_count = added_count
        run.modified_count = modified_count
        run.removed_count = removed_count
        run.finished_at = now

        db.commit()
        return {
            "status": "success",
            "added": added_count,
            "modified": modified_count,
            "removed": removed_count,
            "cursor": state.cursor,
        }

    def _refresh_accounts_and_snapshots(self, db: Session, item_id: int, access_token: str) -> None:
        accounts = self.client.get_accounts(access_token)
        today = date.today()
        for a in accounts:
            existing = db.query(Account).filter(Account.plaid_account_id == a["account_id"]).first()
            if not existing:
                existing = Account(
                    plaid_account_id=a["account_id"],
                    item_id=item_id,
                    name=a.get("name") or "Account",
                )
                db.add(existing)
                db.flush()

            existing.item_id = item_id
            existing.name = a.get("name") or existing.name
            existing.official_name = a.get("official_name")
            existing.mask = a.get("mask")
            existing.type = a.get("type")
            existing.subtype = a.get("subtype")
            existing.current_balance = a.get("current_balance")
            existing.available_balance = a.get("available_balance")
            existing.currency = a.get("iso_currency_code")
            existing.credit_limit = a.get("limit")

            snap = (
                db.query(AccountBalanceSnapshot)
                .filter(
                    AccountBalanceSnapshot.account_id == existing.id,
                    AccountBalanceSnapshot.as_of_date == today,
                )
                .first()
            )
            if snap is None:
                snap = AccountBalanceSnapshot(
                    account_id=existing.id,
                    as_of_date=today,
                    source="accounts_get",
                )
                db.add(snap)
            snap.current_balance = a.get("current_balance")
            snap.available_balance = a.get("available_balance")
            snap.iso_currency_code = a.get("iso_currency_code")
            snap.limit_amount = a.get("limit")
            snap.pulled_at = utcnow()

    def _apply_changes(self, db: Session, item_id: int, payload: dict) -> tuple[int, int, int]:
        added_count = 0
        modified_count = 0
        removed_count = 0

        for t in payload.get("added", []):
            existing = db.query(Transaction).filter(Transaction.plaid_transaction_id == t["transaction_id"]).first()
            if existing:
                continue

            account = self._ensure_account(db, item_id, t["account_id"])
            added_count += 1
            tx_date = t.get("date")
            if isinstance(tx_date, str):
                tx_date = date.fromisoformat(tx_date)

            db.add(
                Transaction(
                    plaid_transaction_id=t["transaction_id"],
                    account_id=account.id,
                    item_id=item_id,
                    date=tx_date,
                    amount=t["amount"],
                    name=t["name"],
                    merchant_name=t.get("merchant_name"),
                    plaid_category_primary=t.get("plaid_category_primary"),
                    pending=t.get("pending", False),
                    raw_json=self._serialize_raw(t),
                )
            )

        for t in payload.get("modified", []):
            existing = db.query(Transaction).filter(Transaction.plaid_transaction_id == t["transaction_id"]).first()
            if existing:
                modified_count += 1
                existing.amount = t["amount"]
                existing.name = t["name"]
                existing.merchant_name = t.get("merchant_name")
                existing.plaid_category_primary = t.get("plaid_category_primary")
                existing.pending = t.get("pending", False)
                existing.raw_json = self._serialize_raw(t)

        for t in payload.get("removed", []):
            existing = db.query(Transaction).filter(Transaction.plaid_transaction_id == t["transaction_id"]).first()
            if existing:
                removed_count += 1
                db.delete(existing)

        return added_count, modified_count, removed_count

    def _ensure_account(self, db: Session, item_id: int, plaid_account_id: str) -> Account:
        account = db.query(Account).filter(Account.plaid_account_id == plaid_account_id).first()
        if not account:
            account = Account(plaid_account_id=plaid_account_id, item_id=item_id, name="Account")
            db.add(account)
            db.flush()
        return account

    @staticmethod
    def _serialize_raw(t: dict) -> str:
        source = t.get("_source")
        if source is not None:
            return json.dumps(source, default=str)
        return json.dumps({k: v for k, v in t.items() if k != "_source"}, default=str)
