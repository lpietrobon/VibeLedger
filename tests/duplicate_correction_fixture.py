"""Small duplicate-correction ledger with an independently authored oracle.

The fixture deliberately contains two same-day/same-amount Market rows and two
same-day/same-amount Coffee rows.  Only the Market pair is eligible for the
explicit correction; the Coffee rows are a guard against similarity-based
automatic hiding.
"""
from datetime import date
from decimal import Decimal

from app.db.session import SessionLocal
from app.models.models import Account, Item, Transaction, TransactionAnnotation
from app.services.security import encrypt_token


def seed_duplicate_correction_ledger():
    """Seed the PI-03 six-row oracle and return stable IDs plus expected totals."""
    with SessionLocal() as db:
        item = Item(
            plaid_item_id="pi15-fixture-item",
            access_token_encrypted=encrypt_token("pi15-fixture-token"),
            status="active",
        )
        db.add(item)
        db.flush()
        checking = Account(
            plaid_account_id="pi15-fixture-checking",
            item_id=item.id,
            name="Checking",
            type="depository",
            subtype="checking",
            currency="USD",
            mask="1234",
        )
        db.add(checking)
        db.flush()

        row_specs = [
            ("paycheck", date(2026, 3, 1), Decimal("-100.00"), "Salary", "INCOME"),
            ("market-a", date(2026, 3, 2), Decimal("25.00"), "Market", "SHOPPING"),
            ("market-b", date(2026, 3, 2), Decimal("25.00"), "Market", "SHOPPING"),
            ("book", date(2026, 3, 3), Decimal("10.00"), "Bookshop", "SHOPPING"),
            ("coffee-a", date(2026, 3, 4), Decimal("7.00"), "Cafe", "FOOD"),
            ("coffee-b", date(2026, 3, 4), Decimal("7.00"), "Cafe", "FOOD"),
        ]
        rows = {}
        for key, txn_date, amount, name, category in row_specs:
            tx = Transaction(
                plaid_transaction_id=f"pi15-{key}",
                account_id=checking.id,
                item_id=item.id,
                date=txn_date,
                amount=amount,
                name=name,
                merchant_name=name,
                plaid_category_primary=category,
                pending=False,
            )
            db.add(tx)
            db.flush()
            rows[key] = tx
            if category != "INCOME":
                db.add(TransactionAnnotation(transaction_id=tx.id, user_category=category))
        db.commit()
        return {
            "item_id": item.id,
            "account_id": checking.id,
            "transaction_ids": {key: tx.id for key, tx in rows.items()},
            "provider_ids": {key: tx.plaid_transaction_id for key, tx in rows.items()},
            "oracle": {
                "income": Decimal("100.00"),
                "expenses_before": Decimal("74.00"),
                "expenses_after": Decimal("49.00"),
                "net_before": Decimal("26.00"),
                "net_after": Decimal("51.00"),
                "before_spend_ids": ["market-a", "market-b", "book", "coffee-a", "coffee-b"],
                "after_spend_ids": ["market-a", "book", "coffee-a", "coffee-b"],
            },
        }
