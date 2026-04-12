from datetime import date

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction, TransactionAnnotation
from app.services.security import encrypt_token


def test_analytics_endpoints_return_lists():
    with TestClient(app) as client:
        for path in [
            "/analytics/monthly-spend",
            "/analytics/category-spend",
            "/analytics/cashflow-trend",
        ]:
            r = client.get(path)
            assert r.status_code == 200
            assert isinstance(r.json(), list)


def _seed_ledger():
    with SessionLocal() as db:
        item = Item(plaid_item_id="i-analytics", access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        account = Account(plaid_account_id="a-analytics", item_id=item.id, name="Checking")
        db.add(account)
        db.flush()

        rows = [
            (date(2026, 3, 1), -1000.0, "Paycheck", "INCOME"),
            (date(2026, 3, 5), 400.0, "Groceries", "FOOD_AND_DRINK"),
            (date(2026, 3, 10), 200.0, "Coffee", "FOOD_AND_DRINK"),
            (date(2026, 4, 1), -1200.0, "Paycheck", "INCOME"),
            (date(2026, 4, 3), 500.0, "Rent", "RENT_AND_UTILITIES"),
        ]
        for d, amt, name, cat in rows:
            db.add(
                Transaction(
                    plaid_transaction_id=f"tx-{d}-{name}",
                    account_id=account.id,
                    item_id=item.id,
                    date=d,
                    amount=amt,
                    name=name,
                    plaid_category_primary=cat,
                    pending=False,
                )
            )
        db.commit()


def test_monthly_spend_only_positive_amounts():
    _seed_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/monthly-spend")
    assert r.status_code == 200
    data = {row["month"]: row["spend"] for row in r.json()}
    assert data["2026-03"] == 600.0
    assert data["2026-04"] == 500.0


def test_monthly_spend_date_filter():
    _seed_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/monthly-spend", params={"start_date": "2026-04-01"})
    assert r.status_code == 200
    months = [row["month"] for row in r.json()]
    assert "2026-03" not in months
    assert "2026-04" in months


def test_cashflow_trend_splits_income_and_expenses():
    _seed_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/cashflow-trend")
    assert r.status_code == 200
    data = {row["month"]: row for row in r.json()}
    assert data["2026-03"]["income"] == 1000.0
    assert data["2026-03"]["expenses"] == 600.0
    assert data["2026-03"]["net"] == 400.0
    assert data["2026-04"]["income"] == 1200.0
    assert data["2026-04"]["expenses"] == 500.0
    assert data["2026-04"]["net"] == 700.0


def test_category_spend_includes_unannotated_transactions():
    _seed_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/category-spend")
    assert r.status_code == 200
    by_cat = {row["category"]: row["spend"] for row in r.json()}
    assert by_cat["FOOD_AND_DRINK"] == 600.0
    assert by_cat["RENT_AND_UTILITIES"] == 500.0
    assert by_cat.get("INCOME", 0) == 0


def test_category_spend_prefers_annotation_over_plaid():
    _seed_ledger()
    with SessionLocal() as db:
        tx = db.query(Transaction).filter(Transaction.name == "Groceries").first()
        db.add(TransactionAnnotation(transaction_id=tx.id, user_category="groceries"))
        db.commit()

    with TestClient(app) as client:
        r = client.get("/analytics/category-spend")
    by_cat = {row["category"]: row["spend"] for row in r.json()}
    assert by_cat["groceries"] == 400.0
    assert by_cat["FOOD_AND_DRINK"] == 200.0
