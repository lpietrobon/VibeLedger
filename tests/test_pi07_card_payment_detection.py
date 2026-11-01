"""Focused PI-07 tests for evidence-qualified reverse card repayments.

These tests supplement the immutable PI-19 contract with the RCA's observed
four-day bound and explicit negative controls.  They use synthetic records only.
"""

from datetime import date, timedelta
from decimal import Decimal

from app.db.session import SessionLocal
from app.models.models import Account, Item, Transaction, TransactionAnnotation, TransferPair
from app.services import transfer_detector


PAYMENT_CATEGORY = "FINANCE/CREDIT_CARD_PAYMENT"


def _seed_pair(*, reverse_days: int, evidence: bool):
    with SessionLocal() as db:
        item = Item(
            plaid_item_id="pi07-item",
            access_token_encrypted="synthetic-token",
            status="active",
        )
        db.add(item)
        db.flush()
        checking = Account(
            plaid_account_id="pi07-checking",
            item_id=item.id,
            name="Checking",
            type="depository",
            subtype="checking",
            currency="USD",
        )
        card = Account(
            plaid_account_id="pi07-card",
            item_id=item.id,
            name="Credit card",
            type="credit",
            subtype="credit card",
            currency="USD",
        )
        db.add_all([checking, card])
        db.flush()
        card_credit = Transaction(
            plaid_transaction_id="pi07-card-credit",
            item_id=item.id,
            account_id=card.id,
            date=date(2032, 1, 1),
            amount=Decimal("-100.00"),
            name="Card credit",
            pending=False,
        )
        checking_outflow = Transaction(
            plaid_transaction_id="pi07-checking-outflow",
            item_id=item.id,
            account_id=checking.id,
            date=date(2032, 1, 1) + timedelta(days=reverse_days),
            amount=Decimal("100.00"),
            name="Card autopay" if evidence else "Ordinary debit",
            pending=False,
        )
        db.add_all([card_credit, checking_outflow])
        db.flush()
        if evidence:
            db.add_all([
                TransactionAnnotation(transaction_id=card_credit.id, rule_category=PAYMENT_CATEGORY),
                TransactionAnnotation(transaction_id=checking_outflow.id, rule_category=PAYMENT_CATEGORY),
            ])
        db.commit()


def test_observed_four_day_reverse_card_payment_is_a_candidate():
    _seed_pair(reverse_days=4, evidence=True)
    with SessionLocal() as db:
        created = transfer_detector.detect_candidates(db)
        assert len(created) == 1
        assert created[0].confirmed is False
        assert db.query(TransferPair).count() == 1


def test_reverse_card_payment_beyond_bounded_exception_stays_unpaired():
    _seed_pair(reverse_days=5, evidence=True)
    with SessionLocal() as db:
        assert transfer_detector.detect_candidates(db) == []


def test_reverse_order_without_payment_evidence_stays_unpaired():
    _seed_pair(reverse_days=2, evidence=False)
    with SessionLocal() as db:
        assert transfer_detector.detect_candidates(db) == []
