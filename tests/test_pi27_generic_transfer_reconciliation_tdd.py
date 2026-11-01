"""Frozen PI-27 contract for deterministic generic transfer reconciliation.

Fixtures are intentionally synthetic and hand-checkable.  They assert the
product distinction between an automatically confirmed movement (exact, unique,
two-sided structured evidence), a review candidate, and an unpaired transaction.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from app.db.session import SessionLocal
from app.models.models import Account, Item, Transaction, TransferPair
from app.services import transfer_detector


def _item(db, key: str) -> Item:
    item = Item(
        plaid_item_id=f"pi27-item-{key}",
        institution_name=f"Synthetic institution {key}",
        access_token_encrypted="synthetic",
        status="active",
    )
    db.add(item)
    db.flush()
    return item


def _account(db, item: Item, key: str, *, kind="depository", subtype="checking") -> Account:
    account = Account(
        plaid_account_id=f"pi27-account-{key}",
        item_id=item.id,
        name=f"Synthetic {key}",
        type=kind,
        subtype=subtype,
        currency="USD",
    )
    db.add(account)
    db.flush()
    return account


def _transaction(db, item, account, key, when, amount, detail=None, name="synthetic movement"):
    raw_json = None
    if detail:
        raw_json = json.dumps({"personal_finance_category": {"detailed": detail}})
    txn = Transaction(
        plaid_transaction_id=f"pi27-txn-{key}",
        item_id=item.id,
        account_id=account.id,
        date=when,
        amount=Decimal(str(amount)),
        name=name,
        pending=False,
        raw_json=raw_json,
    )
    db.add(txn)
    db.flush()
    return txn


def test_generic_two_sided_structured_evidence_auto_confirms_across_account_types():
    """No account type is privileged: the same evidence rule resolves all routes."""
    db = SessionLocal()
    try:
        bank_a = _item(db, "bank-a")
        bank_b = _item(db, "bank-b")
        checking_a = _account(db, bank_a, "checking-a")
        savings_a = _account(db, bank_a, "savings-a", subtype="savings")
        checking_b = _account(db, bank_b, "checking-b")
        card = _account(db, bank_b, "card", kind="credit", subtype="credit card")
        wallet = _account(db, bank_b, "wallet", kind="payment", subtype="wallet")

        pairs = [
            # Same-institution checking to savings.
            (_transaction(db, bank_a, checking_a, "savings-out", date(2032, 1, 10), 101, "TRANSFER_OUT"),
             _transaction(db, bank_a, savings_a, "savings-in", date(2032, 1, 11), -101, "TRANSFER_IN")),
            # Cross-institution checking to checking.
            (_transaction(db, bank_a, checking_a, "other-bank-out", date(2032, 1, 12), 102, "TRANSFER_OUT"),
             _transaction(db, bank_b, checking_b, "other-bank-in", date(2032, 1, 14), -102, "TRANSFER_IN")),
            # Wallet funding.
            (_transaction(db, bank_a, checking_a, "wallet-out", date(2032, 1, 15), 103, "TRANSFER_OUT"),
             _transaction(db, bank_b, wallet, "wallet-in", date(2032, 1, 15), -103, "TRANSFER_IN")),
            # A repayment whose card-side receipt posts first.
            (_transaction(db, bank_a, checking_a, "repayment-out", date(2032, 1, 20), 104, "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"),
             _transaction(db, bank_b, card, "repayment-in", date(2032, 1, 18), -104, "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT")),
        ]
        db.commit()

        created = transfer_detector.detect_candidates(db)

        assert len(created) == 4
        assert all(pair.confirmed for pair in created)
        assert {pair.detected_by for pair in created} == {"auto_confirmed"}
        assert {(pair.txn_out_id, pair.txn_in_id) for pair in created} == {
            (out.id, inn.id) for out, inn in pairs
        }
        assert all(json.loads(pair.decision_evidence)["kind"] == "two_sided_structured" for pair in created)
    finally:
        db.close()


def test_previously_confirmed_exact_route_can_auto_confirm_without_provider_metadata():
    """A user-confirmed route is deterministic reusable evidence, not a fuzzy guess."""
    db = SessionLocal()
    try:
        item = _item(db, "history")
        checking = _account(db, item, "history-checking")
        savings = _account(db, item, "history-savings", subtype="savings")
        old_out = _transaction(db, item, checking, "old-out", date(2032, 2, 1), 40, name="Transfer to rainy day")
        old_in = _transaction(db, item, savings, "old-in", date(2032, 2, 1), -40, name="Transfer from checking")
        db.add(TransferPair(txn_out_id=old_out.id, txn_in_id=old_in.id, detected_by="manual", confirmed=True))
        new_out = _transaction(db, item, checking, "new-out", date(2032, 3, 1), 65, name="Transfer to rainy day")
        new_in = _transaction(db, item, savings, "new-in", date(2032, 3, 2), -65, name="Transfer from checking")
        db.commit()

        created = transfer_detector.detect_candidates(db)

        assert len(created) == 1
        assert created[0].confirmed is True
        assert created[0].detected_by == "auto_confirmed"
        assert json.loads(created[0].decision_evidence)["kind"] == "confirmed_route_signature"
        assert (created[0].txn_out_id, created[0].txn_in_id) == (new_out.id, new_in.id)
    finally:
        db.close()


def test_weak_or_ambiguous_matches_never_auto_exclude_spending():
    """Amount/date, one-sided wording, or a tie may create review evidence only."""
    db = SessionLocal()
    try:
        item = _item(db, "collision")
        checking = _account(db, item, "collision-checking")
        card = _account(db, item, "collision-card", kind="credit", subtype="credit card")
        savings = _account(db, item, "collision-savings", subtype="savings")
        rent = _transaction(db, item, checking, "rent", date(2032, 4, 10), 300, name="Rent portion")
        weak = _transaction(db, item, card, "weak", date(2032, 4, 11), -300, name="Payment received")
        tie_out = _transaction(db, item, checking, "tie-out", date(2032, 4, 12), 50, "TRANSFER_OUT")
        _transaction(db, item, card, "tie-in-a", date(2032, 4, 13), -50, "TRANSFER_IN")
        _transaction(db, item, savings, "tie-in-b", date(2032, 4, 13), -50, "TRANSFER_IN")
        db.commit()

        created = transfer_detector.detect_candidates(db)

        rent_pair = next(pair for pair in created if pair.txn_out_id == rent.id)
        assert rent_pair.confirmed is False
        assert rent_pair.detected_by == "auto"
        assert not any(pair.txn_out_id == tie_out.id for pair in created)
    finally:
        db.close()


def test_auto_confirmation_is_reversible_and_invalidated_when_source_evidence_changes():
    db = SessionLocal()
    try:
        item = _item(db, "lifecycle")
        checking = _account(db, item, "lifecycle-checking")
        savings = _account(db, item, "lifecycle-savings", subtype="savings")
        out = _transaction(db, item, checking, "lifecycle-out", date(2032, 5, 1), 75, "TRANSFER_OUT")
        inn = _transaction(db, item, savings, "lifecycle-in", date(2032, 5, 2), -75, "TRANSFER_IN")
        db.commit()
        pair = transfer_detector.detect_candidates(db)[0]
        assert pair.confirmed is True

        # User reversal is durable across redetection.
        transfer_detector.reject_pair(db, out.id, inn.id)
        db.delete(pair)
        db.commit()
        assert transfer_detector.detect_candidates(db) == []

        # A separate automatic decision must be removed if a provider later
        # changes one source amount, restoring both rows to ordinary accounting.
        other_out = _transaction(db, item, checking, "changed-out", date(2032, 5, 5), 80, "TRANSFER_OUT")
        other_in = _transaction(db, item, savings, "changed-in", date(2032, 5, 6), -80, "TRANSFER_IN")
        db.commit()
        assert transfer_detector.detect_candidates(db)[0].confirmed is True
        other_in.amount = Decimal("-79.99")
        db.commit()

        assert transfer_detector.revalidate_auto_confirmed_pairs(db) == 1
        assert db.query(TransferPair).filter(TransferPair.txn_out_id == other_out.id).count() == 0
    finally:
        db.close()
