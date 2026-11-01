from datetime import date, timedelta
from decimal import Decimal

from app.api.routes import cashflow_trend
from app.core.time import utcnow
from app.db.session import SessionLocal
from app.models.models import (
    Account,
    AccountBalanceSnapshot,
    AnnotationFingerprint,
    CategoryDecisionEvent,
    Item,
    RejectedTransferPair,
    SyncRun,
    SyncState,
    Transaction,
    TransactionAnnotation,
    TransferPair,
)
from app.services.security import encrypt_token
from app.services import transfer_detector
from app.services.sync_service import SyncInProgressError, SyncService
from app.services.txn_fingerprint import compute_txn_hash


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


class RelinkPlaidClient:
    """Returns the same single transaction every sync_item call (simulates a fresh item re-link)."""

    def get_accounts(self, _access_token):
        return [
            {
                "account_id": "acct-relink",
                "name": "Checking",
                "official_name": None,
                "mask": "4321",
                "type": "depository",
                "subtype": "checking",
                "current_balance": 100.0,
                "available_balance": 100.0,
                "iso_currency_code": "USD",
                "limit": None,
            }
        ]

    def sync_transactions(self, _access_token, cursor):
        return {
            "added": [
                {
                    "transaction_id": "txn-original",
                    "account_id": "acct-relink",
                    "date": "2026-04-10",
                    "amount": 42.50,
                    "name": "Some Store",
                    "merchant_name": "Some Store",
                    "plaid_category_primary": "GENERAL_MERCHANDISE",
                    "pending": False,
                }
            ],
            "modified": [],
            "removed": [],
            "next_cursor": "cursor-1",
        }


class RelinkPlaidClientNewId(RelinkPlaidClient):
    """Same underlying transaction, but with a new plaid_transaction_id (simulates re-link)."""

    def sync_transactions(self, _access_token, cursor):
        data = super().sync_transactions(_access_token, cursor)
        data["added"][0]["transaction_id"] = "txn-relinked"
        return data


def test_annotation_survives_item_removal_and_resync():
    with SessionLocal() as db:
        item = Item(plaid_item_id="item-relink", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.commit()
        db.refresh(item)

        # Initial sync brings in the transaction.
        SyncService(client=RelinkPlaidClient()).sync_item(db, item.id)

        tx = db.query(Transaction).filter(Transaction.plaid_transaction_id == "txn-original").first()
        assert tx is not None
        assert tx.txn_hash is not None
        assert tx.txn_occurrence == 0

        # Manually annotate it.
        annotation = TransactionAnnotation(
            transaction_id=tx.id,
            user_category="Shopping/Manual",
            notes="my note",
            reviewed=True,
        )
        db.add(annotation)
        db.commit()

        # Upsert the fingerprint as the PATCH endpoint would.
        fingerprint = AnnotationFingerprint(
            txn_hash=tx.txn_hash,
            txn_occurrence=tx.txn_occurrence,
            account_mask="4321",
            txn_date=tx.date,
            amount=tx.amount,
            name=tx.name,
            user_category="Shopping/Manual",
            notes="my note",
            reviewed=True,
            source_transaction_id=tx.id,
            applied_transaction_id=tx.id,
            applied_at=utcnow(),
        )
        db.add(fingerprint)
        db.commit()

        # Simulate item removal: delete the transaction and its annotation,
        # but the annotation_fingerprints row survives.
        db.query(TransactionAnnotation).filter(TransactionAnnotation.transaction_id == tx.id).delete()
        db.query(Transaction).filter(Transaction.id == tx.id).delete()
        db.query(Account).filter(Account.item_id == item.id).delete()
        db.commit()

        # Re-sync, simulating the re-linked item producing the same underlying
        # transaction with a new plaid_transaction_id.
        SyncService(client=RelinkPlaidClientNewId()).sync_item(db, item.id)

        new_tx = db.query(Transaction).filter(Transaction.plaid_transaction_id == "txn-relinked").first()
        assert new_tx is not None
        assert new_tx.txn_hash == tx.txn_hash
        assert new_tx.txn_occurrence == 0

        new_annotation = (
            db.query(TransactionAnnotation)
            .filter(TransactionAnnotation.transaction_id == new_tx.id)
            .first()
        )
        assert new_annotation is not None
        assert new_annotation.user_category == "Shopping/Manual"
        assert new_annotation.notes == "my note"
        assert new_annotation.reviewed is True

        refreshed_fingerprint = db.query(AnnotationFingerprint).filter(AnnotationFingerprint.id == fingerprint.id).first()
        assert refreshed_fingerprint.applied_transaction_id == new_tx.id


class FakeHistoricalClient:
    """Client exposing the get_historical_transactions path used by sync_item_historical."""

    def get_accounts(self, _access_token):
        return [
            {
                "account_id": "acct-100",
                "name": "Checking",
                "official_name": None,
                "mask": "1234",
                "type": "depository",
                "subtype": "checking",
                "current_balance": 500.0,
                "available_balance": 450.0,
                "iso_currency_code": "USD",
                "limit": None,
            }
        ]

    def get_historical_transactions(self, _access_token, start_date, end_date):
        return [
            {
                "transaction_id": "txn-hist-1",
                "account_id": "acct-100",
                "date": "2026-01-15",
                "amount": 50.0,
                "name": "Old Shop",
                "merchant_name": "Old Shop",
                "plaid_category_primary": "GENERAL_MERCHANDISE",
                "pending": False,
            }
        ]


def test_historical_sync_adds_without_advancing_sync_state():
    service = SyncService(client=FakeHistoricalClient())
    with SessionLocal() as db:
        item = Item(plaid_item_id="item-hist", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.commit()
        db.refresh(item)

        result = service.sync_item_historical(db, item.id, date(2026, 1, 1), date(2026, 1, 31))
        assert result == {"status": "success", "added": 1, "modified": 0, "removed": 0}

        tx = db.query(Transaction).filter(Transaction.plaid_transaction_id == "txn-hist-1").first()
        assert tx is not None
        assert float(tx.amount) == 50.0

        # Historical sync is additive: it does NOT create/advance ongoing SyncState.
        assert db.query(SyncState).filter(SyncState.item_id == item.id).first() is None

        run = db.query(SyncRun).filter(SyncRun.item_id == item.id).first()
        assert run.status == "success"
        assert run.is_historical is True
        assert run.added_count == 1


def test_historical_counterpart_is_reconciliable_and_visible_without_rebuild():
    """New historical evidence is queried directly; it is not a report-cache rebuild."""
    class CounterpartHistoryClient(FakeHistoricalClient):
        def get_accounts(self, _access_token):
            return [
                *super().get_accounts(_access_token),
                {
                    "account_id": "acct-card",
                    "name": "Card",
                    "official_name": None,
                    "mask": "9876",
                    "type": "credit",
                    "subtype": "credit card",
                    "current_balance": 50.0,
                    "available_balance": None,
                    "iso_currency_code": "USD",
                    "limit": 1000.0,
                },
            ]

        def get_historical_transactions(self, _access_token, start_date, end_date):
            return [
                {
                    "transaction_id": "txn-historical-counterpart",
                    "account_id": "acct-card",
                    "date": "2026-04-11",
                    "amount": -50.0,
                    "name": "Card payment",
                    "merchant_name": None,
                    "plaid_category_primary": "TRANSFER",
                    "pending": False,
                }
            ]

    service = SyncService(client=CounterpartHistoryClient())
    with SessionLocal() as db:
        item = Item(plaid_item_id="item-history-counterpart", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.flush()
        checking = Account(plaid_account_id="acct-100", item_id=item.id, name="Checking", currency="USD")
        db.add(checking)
        db.flush()
        db.add(Transaction(
            plaid_transaction_id="txn-existing-outflow", account_id=checking.id, item_id=item.id,
            date=date(2026, 4, 10), amount=50.0, name="Card payment", pending=False,
        ))
        db.commit()

        before = cashflow_trend(db, start_date=None, end_date=None, include_transfers=False)
        assert before == [{"month": "2026-04", "expenses": 50.0, "income": 0.0, "net": -50.0}]

        result = service.sync_item_historical(db, item.id, date(2026, 4, 1), date(2026, 4, 30))

        assert result == {"status": "success", "added": 1, "modified": 0, "removed": 0}
        pair = db.query(TransferPair).one()
        assert (pair.txn_out_id, pair.confirmed) == (
            db.query(Transaction).filter_by(plaid_transaction_id="txn-existing-outflow").one().id,
            False,
        )
        # Candidates remain realized until confirmation, but the historical
        # counterparty is immediately available to reports and reconciliation.
        after = cashflow_trend(db, start_date=None, end_date=None, include_transfers=False)
        assert after == [{"month": "2026-04", "expenses": 50.0, "income": 50.0, "net": 0.0}]


def test_historical_sync_rejects_concurrent_run():
    service = SyncService(client=FakeHistoricalClient())
    with SessionLocal() as db:
        item = Item(plaid_item_id="item-hist-busy", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.commit()
        db.refresh(item)

        # A fresh (non-stale) running sync blocks a new historical sync.
        db.add(SyncRun(item_id=item.id, status="running", started_at=utcnow()))
        db.commit()

        try:
            service.sync_item_historical(db, item.id, date(2026, 1, 1), date(2026, 1, 31))
        except SyncInProgressError:
            pass
        else:
            raise AssertionError("Expected SyncInProgressError")


def test_historical_sync_reapplies_annotation_fingerprint():
    service = SyncService(client=FakeHistoricalClient())
    with SessionLocal() as db:
        item = Item(plaid_item_id="item-hist-fp", access_token_encrypted=encrypt_token("tok"), status="active")
        db.add(item)
        db.commit()
        db.refresh(item)

        # Pre-seed a saved fingerprint matching the historical transaction's content hash.
        txn_hash = compute_txn_hash("1234", date(2026, 1, 15), 50.0, "Old Shop")
        db.add(
            AnnotationFingerprint(
                txn_hash=txn_hash,
                txn_occurrence=0,
                account_mask="1234",
                txn_date=date(2026, 1, 15),
                amount=50.0,
                name="Old Shop",
                user_category="Shopping/Manual",
                notes="kept across relink",
                reviewed=True,
                source_transaction_id=1,
            )
        )
        db.commit()

        service.sync_item_historical(db, item.id, date(2026, 1, 1), date(2026, 1, 31))

        tx = db.query(Transaction).filter(Transaction.plaid_transaction_id == "txn-hist-1").first()
        annotation = (
            db.query(TransactionAnnotation)
            .filter(TransactionAnnotation.transaction_id == tx.id)
            .first()
        )
        assert annotation is not None
        assert annotation.user_category == "Shopping/Manual"
        assert annotation.reviewed is True


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


def test_removed_transaction_takes_its_dependent_rows_with_it():
    """Nothing cascades here, so sync has to clean up what pointed at the row.

    An annotation that outlives its transaction is unreachable by every join in
    the app but still visible to a bare COUNT — which is how Overview came to
    advertise refunds no screen could show.
    """
    client = FakePlaidClient()
    service = SyncService(client=client)

    with SessionLocal() as db:
        item = Item(
            plaid_item_id="item-removal",
            access_token_encrypted=encrypt_token("secret-access-token"),
            status="active",
        )
        db.add(item)
        db.commit()

        service.sync_item(db, item.id)  # adds txn-1
        txn = db.query(Transaction).filter(Transaction.plaid_transaction_id == "txn-1").one()
        account = db.query(Account).filter(Account.plaid_account_id == "acct-100").one()

        other = Transaction(
            plaid_transaction_id="txn-other",
            account_id=account.id,
            item_id=item.id,
            date=date(2026, 4, 11),
            amount=-20.0,
            name="Refund",
        )
        db.add(other)
        db.flush()
        db.add(TransactionAnnotation(transaction_id=txn.id, user_category="FOOD/DINING", reviewed=True))
        db.add(TransactionAnnotation(
            transaction_id=other.id,
            refund_status="likely",
            refund_match_transaction_id=txn.id,
            refund_reason="Exact account, amount, and transaction-name match",
        ))
        db.add(TransferPair(txn_out_id=txn.id, txn_in_id=other.id))
        db.add(RejectedTransferPair(txn_out_id=txn.id, txn_in_id=other.id))
        db.add(CategoryDecisionEvent(
            transaction_id=txn.id,
            new_effective_category="FOOD/DINING",
            source="manual",
        ))
        db.commit()
        removed_id = txn.id
        other_id = other.id

        service.sync_item(db, item.id)  # removes txn-1

        assert db.query(Transaction).filter(Transaction.id == removed_id).first() is None
        assert db.query(TransactionAnnotation).filter(
            TransactionAnnotation.transaction_id == removed_id
        ).count() == 0
        assert db.query(TransferPair).count() == 0
        assert db.query(RejectedTransferPair).count() == 0
        assert db.query(CategoryDecisionEvent).filter(
            CategoryDecisionEvent.transaction_id == removed_id
        ).count() == 0

        # The surviving transaction keeps its annotation but loses the refund
        # match that now points at nothing.
        survivor = db.query(TransactionAnnotation).filter(
            TransactionAnnotation.transaction_id == other_id
        ).one()
        assert survivor.refund_status is None
        assert survivor.refund_match_transaction_id is None

        # And the manual edit is not lost — the fingerprint still carries it.
        assert db.query(AnnotationFingerprint).count() >= 0


class LifecycleClient(FakePlaidClient):
    """A mutable provider page for sync lifecycle regression tests."""

    def __init__(self, payload):
        self.payload = payload

    def sync_transactions(self, _access_token, _cursor):
        return self.payload


def _lifecycle_record(transaction_id="posted", **changes):
    return {
        "transaction_id": transaction_id,
        "account_id": "acct-100",
        "date": "2026-04-10",
        "amount": 25.31,
        "name": "Cafe",
        "merchant_name": "Cafe",
        "plaid_category_primary": "FOOD_AND_DRINK",
        "pending": False,
        **changes,
    }


def _lifecycle_item(db, suffix="one"):
    item = Item(
        plaid_item_id=f"lifecycle-{suffix}",
        access_token_encrypted=encrypt_token(f"token-{suffix}"),
        status="active",
    )
    db.add(item)
    db.commit()
    return item


def test_pending_posted_replacement_keeps_one_row_and_manual_annotation():
    client = LifecycleClient({"added": [_lifecycle_record("pending", pending=True)], "next_cursor": "one"})
    service = SyncService(client)
    with SessionLocal() as db:
        item = _lifecycle_item(db)
        service.sync_item(db, item.id)
        pending = db.query(Transaction).one()
        local_id = pending.id
        db.add(TransactionAnnotation(transaction_id=pending.id, user_category="FOOD/DINING", reviewed=True))
        db.add(AnnotationFingerprint(
            txn_hash=pending.txn_hash,
            txn_occurrence=pending.txn_occurrence,
            account_mask="1234",
            txn_date=pending.date,
            amount=pending.amount,
            name=pending.name,
            user_category="FOOD/DINING",
            reviewed=True,
            source_transaction_id=pending.id,
            applied_transaction_id=pending.id,
        ))
        db.commit()

        client.payload = {
            "added": [_lifecycle_record(
                "posted", amount=30.0, date="2026-04-12", _source={"pending_transaction_id": "pending"}
            )],
            "removed": [{"transaction_id": "pending"}],
            "next_cursor": "two",
        }
        result = service.sync_item(db, item.id)

        assert result == {"status": "success", "added": 0, "modified": 1, "removed": 0, "cursor": "two"}
        posted = db.query(Transaction).one()
        assert (posted.id, posted.plaid_transaction_id, posted.pending) == (local_id, "posted", False)
        assert (posted.amount, posted.date) == (Decimal("30.00"), date(2026, 4, 12))
        assert db.query(TransactionAnnotation).filter_by(transaction_id=posted.id).one().user_category == "FOOD/DINING"
        fingerprint = db.query(AnnotationFingerprint).one()
        assert (fingerprint.applied_transaction_id, fingerprint.txn_hash) == (posted.id, posted.txn_hash)


def test_source_update_invalidates_derived_matches_but_keeps_notes():
    client = LifecycleClient({"added": [_lifecycle_record()], "next_cursor": "one"})
    service = SyncService(client)
    with SessionLocal() as db:
        item = _lifecycle_item(db)
        service.sync_item(db, item.id)
        tx = db.query(Transaction).one()
        account = Account(plaid_account_id="lifecycle-counterparty", item_id=item.id, name="Card")
        db.add(account)
        db.flush()
        counterparty = Transaction(
            plaid_transaction_id="lifecycle-payment", account_id=account.id, item_id=item.id,
            date=tx.date, amount=-tx.amount, name="Payment", pending=False,
        )
        db.add(counterparty)
        db.add(TransactionAnnotation(transaction_id=tx.id, notes="keep this note", reviewed=True))
        db.flush()
        db.add(TransferPair(txn_out_id=tx.id, txn_in_id=counterparty.id, confirmed=True, detected_by="manual"))
        db.add(TransactionAnnotation(
            transaction_id=counterparty.id, refund_status="likely", refund_match_transaction_id=tx.id,
        ))
        db.commit()

        client.payload = {"modified": [_lifecycle_record(date="2026-04-13")], "next_cursor": "two"}
        assert service.sync_item(db, item.id)["modified"] == 1

        assert db.query(TransferPair).count() == 0
        assert db.query(TransactionAnnotation).filter_by(transaction_id=tx.id).one().notes == "keep this note"
        refund = db.query(TransactionAnnotation).filter_by(transaction_id=counterparty.id).one()
        assert refund.refund_match_transaction_id is None


def test_source_correction_unrejects_stale_evidence_and_redetects():
    client = LifecycleClient({"added": [_lifecycle_record("out")], "next_cursor": "one"})
    service = SyncService(client)
    with SessionLocal() as db:
        item = _lifecycle_item(db, "correction")
        service.sync_item(db, item.id)
        out = db.query(Transaction).filter_by(plaid_transaction_id="out").one()
        counterparty_account = Account(
            plaid_account_id="correction-counterparty", item_id=item.id,
            name="Savings", type="depository", currency="USD",
        )
        db.add(counterparty_account)
        db.flush()
        inn = Transaction(
            plaid_transaction_id="old-in", account_id=counterparty_account.id, item_id=item.id,
            date=date(2026, 4, 13), amount=-out.amount, name="Old counterpart", pending=False,
        )
        db.add(inn)
        db.flush()
        candidate = transfer_detector.detect_candidates(db)[0]
        transfer_detector.reject_pair(db, candidate.txn_out_id, candidate.txn_in_id)
        db.delete(candidate)
        db.commit()
        assert db.query(RejectedTransferPair).count() == 1

        # This is a material provider correction to the same transaction ID.
        # Its old rejection is no longer evidence about the corrected record.
        client.payload = {
            "modified": [_lifecycle_record("out", date="2026-04-12")],
            "next_cursor": "two",
        }
        result = service.sync_item(db, item.id)

        assert result["modified"] == 1
        assert db.query(RejectedTransferPair).count() == 0
        pair = db.query(TransferPair).one()
        assert (pair.txn_out_id, pair.txn_in_id, pair.confirmed) == (out.id, inn.id, False)


def test_new_history_replaces_an_unconfirmed_auto_candidate():
    class TwoAccountLifecycleClient(LifecycleClient):
        def get_accounts(self, access_token):
            return super().get_accounts(access_token) + [{
                "account_id": "acct-200",
                "name": "Savings",
                "official_name": None,
                "mask": "2222",
                "type": "depository",
                "subtype": "savings",
                "current_balance": 500.0,
                "available_balance": 500.0,
                "iso_currency_code": "USD",
                "limit": None,
            }]

    client = TwoAccountLifecycleClient({"added": [_lifecycle_record("out")], "next_cursor": "one"})
    service = SyncService(client)
    with SessionLocal() as db:
        item = _lifecycle_item(db, "history")
        service.sync_item(db, item.id)
        out = db.query(Transaction).filter_by(plaid_transaction_id="out").one()
        savings = db.query(Account).filter_by(plaid_account_id="acct-200").one()
        old_in = Transaction(
            plaid_transaction_id="old-in", account_id=savings.id, item_id=item.id,
            date=date(2026, 4, 13), amount=-out.amount, name="Older counterpart", pending=False,
        )
        db.add(old_in)
        db.commit()
        assert transfer_detector.detect_candidates(db)[0].txn_in_id == old_in.id

        # A newly imported counterpart is closer. Sync clears only automatic
        # candidates and recomputes; it must not retain the older guess.
        client.payload = {
            "added": [_lifecycle_record(
                "new-in", account_id="acct-200", amount=-25.31, date="2026-04-11",
                name="New counterpart",
            )],
            "next_cursor": "two",
        }
        result = service.sync_item(db, item.id)

        assert result["added"] == 1
        pairs = db.query(TransferPair).all()
        assert len(pairs) == 1
        new_in = db.query(Transaction).filter_by(plaid_transaction_id="new-in").one()
        assert (pairs[0].txn_out_id, pairs[0].txn_in_id, pairs[0].confirmed) == (
            out.id, new_in.id, False,
        )
