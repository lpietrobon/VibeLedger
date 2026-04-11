import json
from datetime import datetime, date
from sqlalchemy.orm import Session
from app.models.models import Account, AccountBalanceSnapshot, Item, SyncRun, SyncState, Transaction
from app.services.plaid_client import PlaidClient
from app.services.security import decrypt_token


class SyncService:
    def __init__(self, client: PlaidClient | None = None):
        self.client = client or PlaidClient()

    def sync_item(self, db: Session, item_id: int) -> dict:
        item = db.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError("item not found")

        state = db.query(SyncState).filter(SyncState.item_id == item_id).first()
        if not state:
            state = SyncState(item_id=item_id, cursor=None)
            db.add(state)
            db.flush()

        run = SyncRun(item_id=item_id, status="running")
        db.add(run)
        db.flush()

        access_token = decrypt_token(item.access_token_encrypted)
        self._refresh_accounts_and_snapshots(db, item_id, access_token)
        data = self.client.sync_transactions(access_token, state.cursor)
        added_count, modified_count, removed_count = self._apply_changes(db, item_id, data)

        state.cursor = data.get("next_cursor")
        state.last_sync_at = datetime.utcnow()
        state.last_success_at = datetime.utcnow()
        state.last_error_code = None
        state.last_error_message = None
        state.consecutive_failures = 0

        run.status = "success"
        run.added_count = added_count
        run.modified_count = modified_count
        run.removed_count = removed_count
        run.finished_at = datetime.utcnow()

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

            snap = AccountBalanceSnapshot(
                account_id=existing.id,
                as_of_date=today,
                current_balance=a.get("current_balance"),
                available_balance=a.get("available_balance"),
                iso_currency_code=a.get("iso_currency_code"),
                limit_amount=a.get("limit"),
                source="accounts_get",
            )
            db.add(snap)

    def _apply_changes(self, db: Session, item_id: int, payload: dict) -> tuple[int, int, int]:
        added_count = 0
        modified_count = 0
        removed_count = 0

        for t in payload.get("added", []):
            account = db.query(Account).filter(Account.plaid_account_id == t["account_id"]).first()
            if not account:
                account = Account(plaid_account_id=t["account_id"], item_id=item_id, name="Account")
                db.add(account)
                db.flush()

            existing = db.query(Transaction).filter(Transaction.plaid_transaction_id == t["transaction_id"]).first()
            if existing:
                modified_count += 1
                existing.amount = t["amount"]
                existing.name = t["name"]
                existing.merchant_name = t.get("merchant_name")
                existing.plaid_category_primary = t.get("plaid_category_primary")
                existing.pending = t.get("pending", False)
                existing.raw_json = json.dumps(t)
            else:
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
                        raw_json=json.dumps(t),
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
                existing.raw_json = json.dumps(t)

        for t in payload.get("removed", []):
            existing = db.query(Transaction).filter(Transaction.plaid_transaction_id == t["transaction_id"]).first()
            if existing:
                removed_count += 1
                db.delete(existing)

        return added_count, modified_count, removed_count
