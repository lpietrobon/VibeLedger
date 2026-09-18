"""PI-31: conservative reconciliation when a card receipt is miscategorizied."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from app.db.session import SessionLocal
from app.models.models import Account, Item, Transaction
from app.services import transfer_detector


DETAIL_PAYMENT = "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"
DETAIL_WAGES = "INCOME_WAGES"


def _setup():
    db = SessionLocal()
    item = Item(plaid_item_id="pi31-item", access_token_encrypted="synthetic", status="active")
    db.add(item)
    db.flush()
    checking = Account(
        plaid_account_id="pi31-checking", item_id=item.id, name="Checking",
        type="depository", subtype="checking", currency="USD",
    )
    card = Account(
        plaid_account_id="pi31-card", item_id=item.id, name="Card",
        type="credit", subtype="credit card", currency="USD",
    )
    savings = Account(
        plaid_account_id="pi31-savings", item_id=item.id, name="Savings",
        type="depository", subtype="savings", currency="USD",
    )
    db.add_all([checking, card, savings])
    db.flush()
    return db, item, checking, card, savings


def _txn(db, item, account, key, when, amount, name, detail):
    txn = Transaction(
        plaid_transaction_id=f"pi31-{key}", item_id=item.id, account_id=account.id,
        date=when, amount=Decimal(str(amount)), name=name, pending=False,
        raw_json=json.dumps({"personal_finance_category": {"detailed": detail}}),
    )
    db.add(txn)
    db.flush()
    return txn


def test_one_sided_structured_card_repayment_auto_confirms_without_issuer_specific_text():
    db, item, checking, card, _ = _setup()
    try:
        out = _txn(
            db, item, checking, "out", date(2035, 1, 14), 412.34,
            "Issuer debit 350112 with changing opaque data", DETAIL_PAYMENT,
        )
        inn = _txn(
            db, item, card, "in", date(2035, 1, 12), -412.34,
            "Automatic payment received", DETAIL_WAGES,
        )
        db.commit()

        pair = transfer_detector.detect_candidates(db)[0]

        assert pair.confirmed is True
        assert pair.detected_by == "auto_confirmed"
        assert (pair.txn_out_id, pair.txn_in_id) == (out.id, inn.id)
        evidence = json.loads(pair.decision_evidence)
        assert evidence["kind"] == "one_sided_structured_card_repayment"
        assert evidence["out_provider_detail"] == DETAIL_PAYMENT
        assert evidence["receipt_date_token"] == "350112"
    finally:
        db.close()


def test_structured_checking_leg_abstains_without_card_side_payment_evidence():
    db, item, checking, card, _ = _setup()
    try:
        out = _txn(db, item, checking, "weak-out", date(2035, 2, 10), 90, "Card debit 350211", DETAIL_PAYMENT)
        _txn(db, item, card, "weak-in", date(2035, 2, 11), -90, "Promotional credit", DETAIL_WAGES)
        db.commit()

        pair = transfer_detector.detect_candidates(db)[0]

        assert pair.txn_out_id == out.id
        assert pair.confirmed is False
        assert pair.detected_by == "auto"
    finally:
        db.close()


def test_payment_wording_abstains_when_embedded_date_does_not_match_receipt():
    db, item, checking, card, _ = _setup()
    try:
        out = _txn(
            db, item, checking, "wrong-date-out", date(2035, 2, 12), 90,
            "Issuer payment 350209", DETAIL_PAYMENT,
        )
        _txn(
            db, item, card, "wrong-date-in", date(2035, 2, 11), -90,
            "Payment received", DETAIL_WAGES,
        )
        db.commit()

        pair = transfer_detector.detect_candidates(db)[0]

        assert pair.confirmed is False
    finally:
        db.close()


def test_structured_payment_detail_abstains_for_non_card_destination():
    db, item, checking, _, savings = _setup()
    try:
        out = _txn(db, item, checking, "route-out", date(2035, 3, 10), 90, "Card debit", DETAIL_PAYMENT)
        _txn(db, item, savings, "route-in", date(2035, 3, 11), -90, "Payment received", DETAIL_WAGES)
        db.commit()

        pair = transfer_detector.detect_candidates(db)[0]

        assert pair.txn_out_id == out.id
        assert pair.confirmed is False
    finally:
        db.close()


def test_equal_nearest_counterparts_remain_unpaired_despite_strong_leg_evidence():
    db, item, checking, card, savings = _setup()
    try:
        _txn(db, item, checking, "tie-out", date(2035, 4, 10), 90, "Card debit", DETAIL_PAYMENT)
        _txn(db, item, card, "tie-card", date(2035, 4, 11), -90, "Payment received", DETAIL_WAGES)
        _txn(db, item, savings, "tie-savings", date(2035, 4, 11), -90, "Payment received", DETAIL_WAGES)
        db.commit()

        assert transfer_detector.detect_candidates(db) == []
    finally:
        db.close()
