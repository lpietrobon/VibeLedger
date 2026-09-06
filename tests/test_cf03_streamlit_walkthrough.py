"""Executable CF-03 walkthrough for the maintained Streamlit presentation.

This is intentionally small: it proves that the principal cashflow views can
render the same disposable ledger in monthly and yearly modes. The React route
walkthrough covers transaction review behavior separately.
"""

from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from app.db.schema_patches import apply_patches
from app.db.session import SessionLocal, engine
from app.models.models import Account, Item, Transaction, TransactionAnnotation, TransferPair


def _seed_walkthrough_ledger() -> None:
    apply_patches(engine)
    with SessionLocal() as db:
        item = Item(plaid_item_id="cf03", access_token_encrypted="synthetic")
        db.add(item)
        db.flush()
        checking = Account(
            plaid_account_id="cf03-checking",
            item_id=item.id,
            name="Checking",
            type="depository",
            currency="USD",
            current_balance=3000,
        )
        card = Account(
            plaid_account_id="cf03-card",
            item_id=item.id,
            name="Card",
            type="credit",
            currency="USD",
            current_balance=500,
        )
        db.add_all([checking, card])
        db.flush()

        rows = [
            ("Salary", checking, -3000, date(2024, 3, 1), "INCOME"),
            ("Dinner", card, 120, date(2024, 3, 5), "FOOD_AND_DRINK"),
            ("Rent", checking, 1500, date(2024, 3, 2), "RENT_AND_UTILITIES"),
            ("Dinner prior", card, 80, date(2024, 2, 5), "FOOD_AND_DRINK"),
            ("Rent prior", checking, 1500, date(2024, 2, 2), "RENT_AND_UTILITIES"),
            ("Card payment", checking, 500, date(2024, 3, 6), "TRANSFER_OUT"),
            ("Card receipt", card, -500, date(2024, 3, 7), "TRANSFER_IN"),
            ("Odd charge", card, 777, date(2024, 3, 8), "UNCATEGORIZED"),
        ]
        ids: list[int] = []
        for index, (name, account, amount, posted, category) in enumerate(rows):
            transaction = Transaction(
                plaid_transaction_id=f"cf03-{index}",
                item_id=item.id,
                account_id=account.id,
                name=name,
                amount=amount,
                date=posted,
                plaid_category_primary=category,
                pending=False,
            )
            db.add(transaction)
            db.flush()
            ids.append(transaction.id)
        db.add(TransferPair(txn_out_id=ids[5], txn_in_id=ids[6], confirmed=True))
        db.add(TransactionAnnotation(transaction_id=ids[7], reviewed=False))
        db.commit()


def test_streamlit_cashflow_walkthrough() -> None:
    _seed_walkthrough_ledger()
    db_path = str(engine.url.database)

    app = AppTest.from_file(Path(__file__).parents[1] / "Spend.py", default_timeout=20)
    app.session_state["db_path"] = db_path
    app.run()

    assert not app.exception
    assert [title.value for title in app.title] == ["Overview"]
    overview = " ".join(markdown.value for markdown in app.markdown)
    assert "Month spending" in overview
    assert "vs last month" in overview
    assert any(metric.label == "Uncategorized transactions" for metric in app.metric)

    app.switch_page("pages/2_Spending.py").run()
    assert not app.exception
    assert [title.value for title in app.title] == ["Spending"]
    assert app.segmented_control[0].value == "Monthly"

    app.segmented_control[0].set_value("Yearly").run()
    assert not app.exception
    assert app.segmented_control[0].value == "Yearly"
    spending = " ".join(markdown.value for markdown in app.markdown)
    assert "2024 spend" in spending
    assert "Top driver" in spending
