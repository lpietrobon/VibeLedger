from datetime import date
from decimal import Decimal

from app.db.session import SessionLocal
from app.models.models import Account, Item, Transaction, TransferPair
from app.services import transfer_detector


def _seed_item_and_accounts(db) -> tuple[Item, Account, Account]:
    item = Item(
        plaid_item_id="itm-test",
        institution_name="Test Bank",
        access_token_encrypted="x",
        status="active",
    )
    db.add(item)
    db.flush()
    checking = Account(
        plaid_account_id="ac-check",
        item_id=item.id,
        name="Checking",
        type="depository",
        subtype="checking",
        current_balance=Decimal("1000.00"),
    )
    credit = Account(
        plaid_account_id="ac-credit",
        item_id=item.id,
        name="CC",
        type="credit",
        subtype="credit card",
        current_balance=Decimal("250.00"),
    )
    db.add_all([checking, credit])
    db.flush()
    return item, checking, credit


def _mk_txn(db, item, account, amount, d, name="tx"):
    t = Transaction(
        plaid_transaction_id=f"tx-{name}-{account.id}-{d}",
        account_id=account.id,
        item_id=item.id,
        date=d,
        amount=Decimal(str(amount)),
        name=name,
        pending=False,
    )
    db.add(t)
    db.flush()
    return t


def test_detects_exact_same_day_pair():
    db = SessionLocal()
    try:
        item, checking, credit = _seed_item_and_accounts(db)
        _mk_txn(db, item, checking, 100, date(2024, 1, 10), "CC payment out")
        _mk_txn(db, item, credit, -100, date(2024, 1, 10), "CC payment in")
        db.commit()

        created = transfer_detector.detect_candidates(db)
        assert len(created) == 1
        assert db.query(TransferPair).count() == 1
    finally:
        db.close()


def test_ignores_wide_gap():
    db = SessionLocal()
    try:
        item, checking, credit = _seed_item_and_accounts(db)
        _mk_txn(db, item, checking, 100, date(2024, 1, 10), "out")
        _mk_txn(db, item, credit, -100, date(2024, 1, 20), "in")
        db.commit()

        created = transfer_detector.detect_candidates(db, window_days=3)
        assert created == []
    finally:
        db.close()


def test_idempotent_on_second_run():
    db = SessionLocal()
    try:
        item, checking, credit = _seed_item_and_accounts(db)
        _mk_txn(db, item, checking, 100, date(2024, 1, 10), "out")
        _mk_txn(db, item, credit, -100, date(2024, 1, 11), "in")
        db.commit()

        first = transfer_detector.detect_candidates(db)
        second = transfer_detector.detect_candidates(db)
        assert len(first) == 1
        assert second == []
        assert db.query(TransferPair).count() == 1
    finally:
        db.close()


def test_does_not_pair_same_account():
    db = SessionLocal()
    try:
        item, checking, _ = _seed_item_and_accounts(db)
        _mk_txn(db, item, checking, 100, date(2024, 1, 10), "a")
        _mk_txn(db, item, checking, -100, date(2024, 1, 10), "b")
        db.commit()

        assert transfer_detector.detect_candidates(db) == []
    finally:
        db.close()


def test_manual_pair_rejects_same_account():
    db = SessionLocal()
    try:
        item, checking, _ = _seed_item_and_accounts(db)
        a = _mk_txn(db, item, checking, 50, date(2024, 2, 1), "a")
        b = _mk_txn(db, item, checking, -50, date(2024, 2, 1), "b")
        db.commit()
        try:
            transfer_detector.manual_pair(db, a.id, b.id)
            assert False, "should have raised"
        except ValueError:
            pass
    finally:
        db.close()
