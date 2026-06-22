import json
from datetime import date

from app.db.session import SessionLocal
from app.models.models import Account, Item, Transaction, TransactionAnnotation
from app.services.refund_detector import classify_refunds
from app.services.security import encrypt_token


def _seed_account():
    db = SessionLocal()
    item = Item(plaid_item_id="refund-item", access_token_encrypted=encrypt_token("t"), status="active")
    db.add(item)
    db.flush()
    account = Account(plaid_account_id="refund-account", item_id=item.id, name="Card")
    db.add(account)
    db.flush()
    return db, item, account


def test_exact_later_credit_is_likely_refund():
    db, item, account = _seed_account()
    charge = Transaction(
        plaid_transaction_id="charge",
        account_id=account.id,
        item_id=item.id,
        date=date(2025, 12, 29),
        amount=1576.22,
        name="AIRBNB * HMXPY5P3EX",
        plaid_category_primary="TRAVEL",
        pending=False,
    )
    refund = Transaction(
        plaid_transaction_id="refund",
        account_id=account.id,
        item_id=item.id,
        date=date(2026, 6, 1),
        amount=-1576.22,
        name="AIRBNB * HMXPY5P3EX",
        plaid_category_primary="TRAVEL",
        pending=False,
    )
    db.add_all([charge, refund])
    db.commit()

    result = classify_refunds(db)
    annotation = db.query(TransactionAnnotation).filter_by(transaction_id=refund.id).one()

    assert result == {"likely": 1, "confirmed": 0}
    assert annotation.refund_status == "likely"
    assert annotation.refund_match_transaction_id == charge.id
    db.close()


def test_income_and_nonmatching_credit_are_not_refunds():
    db, item, account = _seed_account()
    db.add_all(
        [
            Transaction(
                plaid_transaction_id="income",
                account_id=account.id,
                item_id=item.id,
                date=date(2026, 6, 1),
                amount=-2000,
                name="PAYROLL",
                plaid_category_primary="INCOME",
                pending=False,
            ),
            Transaction(
                plaid_transaction_id="unmatched",
                account_id=account.id,
                item_id=item.id,
                date=date(2026, 6, 2),
                amount=-25,
                name="CARD REWARD",
                plaid_category_primary="GENERAL_SERVICES",
                pending=False,
            ),
        ]
    )
    db.commit()

    result = classify_refunds(db)
    assert result == {"likely": 0, "confirmed": 0}
    assert db.query(TransactionAnnotation).count() == 1
    assert db.query(TransactionAnnotation).one().refund_status is None
    db.close()


def test_plaid_refund_code_is_confirmed_and_manual_override_is_preserved():
    db, item, account = _seed_account()
    coded = Transaction(
        plaid_transaction_id="coded",
        account_id=account.id,
        item_id=item.id,
        date=date(2026, 6, 3),
        amount=-10,
        name="RETURN",
        plaid_category_primary="GENERAL_MERCHANDISE",
        pending=False,
        raw_json=json.dumps({"transaction_code": "refund"}),
    )
    manual = Transaction(
        plaid_transaction_id="manual",
        account_id=account.id,
        item_id=item.id,
        date=date(2026, 6, 4),
        amount=-20,
        name="ADJUSTMENT",
        plaid_category_primary="GENERAL_MERCHANDISE",
        pending=False,
    )
    db.add_all([coded, manual])
    db.flush()
    db.add(TransactionAnnotation(transaction_id=manual.id, refund_status="not_refund"))
    db.commit()

    result = classify_refunds(db)
    assert result == {"likely": 0, "confirmed": 1}
    assert db.query(TransactionAnnotation).filter_by(transaction_id=coded.id).one().refund_status == "confirmed"
    assert db.query(TransactionAnnotation).filter_by(transaction_id=manual.id).one().refund_status == "not_refund"
    db.close()
