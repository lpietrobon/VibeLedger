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


def _mk_txn(db, item, account, amount, d, name="tx", category=None):
    t = Transaction(
        plaid_transaction_id=f"tx-{name}-{account.id}-{d}",
        account_id=account.id,
        item_id=item.id,
        date=d,
        amount=Decimal(str(amount)),
        name=name,
        plaid_category_primary=category,
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

        assert transfer_detector.detect_candidates(db, window_days=3) == []
    finally:
        db.close()


def test_inflow_before_outflow_is_not_a_transfer():
    """Money must leave before it arrives. Allowing the reverse doubles the
    window in which unrelated equal amounts can collide."""
    db = SessionLocal()
    try:
        item, checking, credit = _seed_item_and_accounts(db)
        _mk_txn(db, item, credit, -100, date(2024, 1, 10), "arrives first")
        _mk_txn(db, item, checking, 100, date(2024, 1, 12), "leaves later")
        db.commit()

        assert transfer_detector.detect_candidates(db, window_days=3) == []
    finally:
        db.close()


def test_refuses_to_guess_between_tied_candidates():
    """Two identical inflows equally close to one outflow: pairing either would
    be a coin flip that silently removes money from analytics."""
    db = SessionLocal()
    try:
        item, checking, credit = _seed_item_and_accounts(db)
        third = Account(plaid_account_id="ac-3", item_id=item.id, name="Savings", type="depository")
        db.add(third)
        db.flush()

        _mk_txn(db, item, checking, 50, date(2024, 1, 10), "out")
        _mk_txn(db, item, credit, -50, date(2024, 1, 11), "candidate a")
        _mk_txn(db, item, third, -50, date(2024, 1, 11), "candidate b")
        db.commit()

        assert transfer_detector.detect_candidates(db) == []
    finally:
        db.close()


def test_prefers_the_closer_candidate_when_not_tied():
    db = SessionLocal()
    try:
        item, checking, credit = _seed_item_and_accounts(db)
        third = Account(plaid_account_id="ac-3", item_id=item.id, name="Savings", type="depository")
        db.add(third)
        db.flush()

        out = _mk_txn(db, item, checking, 50, date(2024, 1, 10), "out")
        near = _mk_txn(db, item, credit, -50, date(2024, 1, 10), "same day")
        _mk_txn(db, item, third, -50, date(2024, 1, 13), "three days later")
        db.commit()

        created = transfer_detector.detect_candidates(db)
        assert len(created) == 1
        assert created[0].txn_out_id == out.id
        assert created[0].txn_in_id == near.id
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


def test_unrelated_equal_amounts_still_pair_accepted_limitation():
    """ACCEPTED LIMITATION, pinned deliberately.

    Cards paid from an account that is NOT linked leave one-sided payments, so
    ideally nothing here would pair. But with only amount + date +
    different-account to go on, a rent payment and a card payment of the same
    size within the window are indistinguishable from a real transfer, and one
    pair is produced.

    The chosen mitigation is visibility rather than precision: the transaction
    list shows both rows with a Transfer badge, and unpairing is remembered (see
    test_unpairing_is_remembered_across_redetection) so a correction sticks.
    Adding a discriminator — a consumption-category veto, or matching the
    counterparty account name in the description — would eliminate this at the
    cost of complexity, and was deliberately deferred.
    """
    db = SessionLocal()
    try:
        item, checking, amex = _seed_item_and_accounts(db)
        visa = Account(plaid_account_id="ac-visa", item_id=item.id, name="Visa", type="credit")
        db.add(visa)
        db.flush()

        # Card payments arriving from the unlinked payer — no counterparty here.
        _mk_txn(db, item, amex, -500, date(2024, 3, 10), "PAYMENT THANK YOU", "LOAN_PAYMENTS")
        _mk_txn(db, item, visa, -300, date(2024, 3, 12), "ONLINE PAYMENT", "LOAN_PAYMENTS")
        # Ordinary activity that merely shares an amount with one of them.
        _mk_txn(db, item, checking, 300, date(2024, 3, 11), "RENT PORTION", "RENT_AND_UTILITIES")
        _mk_txn(db, item, amex, 500, date(2024, 3, 8), "FLIGHT BOOKING", "TRAVEL")
        _mk_txn(db, item, checking, -2000, date(2024, 3, 1), "ACME PAYROLL", "INCOME")
        db.commit()

        created = transfer_detector.detect_candidates(db)
        paired_names = sorted(
            (db.get(Transaction, p.txn_out_id).name, db.get(Transaction, p.txn_in_id).name)
            for p in created
        )
        # The genuine one-sided payments stay unpaired; only the amount
        # coincidence pairs.
        assert paired_names == [("RENT PORTION", "ONLINE PAYMENT")]
    finally:
        db.close()


def test_unpairing_is_remembered_across_redetection():
    """Detection re-runs after every sync. Without a memory of rejections, an
    unpaired false positive reappears immediately and the review page is a
    treadmill."""
    db = SessionLocal()
    try:
        item, checking, credit = _seed_item_and_accounts(db)
        out = _mk_txn(db, item, checking, 300, date(2024, 3, 11), "RENT PORTION")
        inn = _mk_txn(db, item, credit, -300, date(2024, 3, 12), "ONLINE PAYMENT")
        db.commit()

        created = transfer_detector.detect_candidates(db)
        assert len(created) == 1

        # The user unpairs it.
        transfer_detector.reject_pair(db, out.id, inn.id)
        db.query(TransferPair).delete()
        db.commit()

        assert transfer_detector.detect_candidates(db) == []
        assert db.query(TransferPair).count() == 0

        # Manually pairing them later overrides the rejection.
        transfer_detector.manual_pair(db, out.id, inn.id)
        assert db.query(TransferPair).count() == 1
    finally:
        db.close()


def test_clear_auto_pairs_keeps_confirmed_and_manual():
    db = SessionLocal()
    try:
        item, checking, credit = _seed_item_and_accounts(db)
        a = _mk_txn(db, item, checking, 100, date(2024, 1, 10), "out-a")
        b = _mk_txn(db, item, credit, -100, date(2024, 1, 10), "in-a")
        c = _mk_txn(db, item, checking, 70, date(2024, 2, 10), "out-b")
        d = _mk_txn(db, item, credit, -70, date(2024, 2, 10), "in-b")
        db.add_all([
            TransferPair(txn_out_id=a.id, txn_in_id=b.id, detected_by="auto", confirmed=False),
            TransferPair(txn_out_id=c.id, txn_in_id=d.id, detected_by="manual", confirmed=True),
        ])
        db.commit()

        assert transfer_detector.clear_auto_pairs(db) == 1
        remaining = db.query(TransferPair).all()
        assert len(remaining) == 1
        assert remaining[0].detected_by == "manual"
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
