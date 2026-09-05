from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction, TransactionAnnotation, TransferPair
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def test_analytics_endpoints_return_lists():
    with TestClient(app) as client:
        for path in [
            "/analytics/monthly-spend",
            "/analytics/category-spend",
            "/analytics/cashflow-trend",
        ]:
            r = client.get(path, headers=AUTH_HEADERS)
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
        r = client.get("/analytics/monthly-spend", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = {row["month"]: row["spend"] for row in r.json()}
    assert data["2026-03"] == 600.0
    assert data["2026-04"] == 500.0


def test_monthly_spend_date_filter():
    _seed_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/monthly-spend", params={"start_date": "2026-04-01"}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    months = [row["month"] for row in r.json()]
    assert "2026-03" not in months
    assert "2026-04" in months


def test_cashflow_trend_splits_income_and_expenses():
    _seed_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/cashflow-trend", headers=AUTH_HEADERS)
    assert r.status_code == 200
    data = {row["month"]: row for row in r.json()}
    assert data["2026-03"]["income"] == 1000.0
    assert data["2026-03"]["expenses"] == 600.0
    assert data["2026-03"]["net"] == 400.0
    assert data["2026-04"]["income"] == 1200.0
    assert data["2026-04"]["expenses"] == 500.0
    assert data["2026-04"]["net"] == 700.0


def test_refund_reduces_spend_instead_of_counting_as_income():
    _seed_ledger()
    with SessionLocal() as db:
        account = db.query(Account).filter(Account.plaid_account_id == "a-analytics").one()
        item = db.query(Item).filter(Item.plaid_item_id == "i-analytics").one()
        refund = Transaction(
            plaid_transaction_id="tx-refund",
            account_id=account.id,
            item_id=item.id,
            date=date(2026, 3, 15),
            amount=-200.0,
            name="Coffee refund",
            plaid_category_primary="FOOD_AND_DRINK",
            pending=False,
        )
        db.add(refund)
        db.flush()
        db.add(TransactionAnnotation(transaction_id=refund.id, refund_status="likely"))
        db.commit()

    with TestClient(app) as client:
        monthly = client.get("/analytics/monthly-spend", headers=AUTH_HEADERS).json()
        cashflow = client.get("/analytics/cashflow-trend", headers=AUTH_HEADERS).json()
        categories = client.get("/analytics/category-spend", headers=AUTH_HEADERS).json()

    assert {row["month"]: row["spend"] for row in monthly}["2026-03"] == 400.0
    march = {row["month"]: row for row in cashflow}["2026-03"]
    assert march["expenses"] == 400.0
    assert march["income"] == 1000.0
    assert march["net"] == 600.0
    assert {row["category"]: row["spend"] for row in categories}["FOOD/OTHER"] == 400.0


def test_category_spend_includes_unannotated_transactions():
    _seed_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/category-spend", headers=AUTH_HEADERS)
    assert r.status_code == 200
    by_cat = {row["category"]: row["spend"] for row in r.json()}
    assert by_cat["FOOD/OTHER"] == 600.0
    assert by_cat["HOUSING/RENT_AND_UTILITIES"] == 500.0
    assert by_cat.get("INCOME", 0) == 0


def test_category_spend_prefers_annotation_over_plaid():
    _seed_ledger()
    with SessionLocal() as db:
        tx = db.query(Transaction).filter(Transaction.name == "Groceries").first()
        db.add(TransactionAnnotation(transaction_id=tx.id, user_category="groceries"))
        db.commit()

    with TestClient(app) as client:
        r = client.get("/analytics/category-spend", headers=AUTH_HEADERS)
    by_cat = {row["category"]: row["spend"] for row in r.json()}
    assert by_cat["groceries"] == 400.0
    assert by_cat["FOOD/OTHER"] == 200.0


def test_posted_analytics_and_spend_drilldown_share_the_same_rows():
    """Pending rows and confirmed transfers cannot inflate the trusted total."""
    _seed_ledger()
    with SessionLocal() as db:
        item = db.query(Item).filter_by(plaid_item_id="i-analytics").one()
        checking = db.query(Account).filter_by(plaid_account_id="a-analytics").one()
        savings = Account(plaid_account_id="a-analytics-savings", item_id=item.id, name="Savings")
        db.add(savings)
        db.flush()

        pending = Transaction(
            plaid_transaction_id="tx-pending", account_id=checking.id, item_id=item.id,
            date=date(2026, 3, 16), amount=99.0, name="Pending card authorization", pending=True,
        )
        candidate_out = Transaction(
            plaid_transaction_id="tx-candidate-out", account_id=checking.id, item_id=item.id,
            date=date(2026, 3, 17), amount=50.0, name="Possible transfer", pending=False,
        )
        candidate_in = Transaction(
            plaid_transaction_id="tx-candidate-in", account_id=savings.id, item_id=item.id,
            date=date(2026, 3, 17), amount=-50.0, name="Possible transfer", pending=False,
        )
        confirmed_out = Transaction(
            plaid_transaction_id="tx-confirmed-out", account_id=checking.id, item_id=item.id,
            date=date(2026, 3, 18), amount=30.0, name="Confirmed transfer", pending=False,
        )
        confirmed_in = Transaction(
            plaid_transaction_id="tx-confirmed-in", account_id=savings.id, item_id=item.id,
            date=date(2026, 3, 18), amount=-30.0, name="Confirmed transfer", pending=False,
        )
        db.add_all([pending, candidate_out, candidate_in, confirmed_out, confirmed_in])
        db.flush()
        db.add(TransferPair(txn_out_id=candidate_out.id, txn_in_id=candidate_in.id, confirmed=False))
        db.add(TransferPair(txn_out_id=confirmed_out.id, txn_in_id=confirmed_in.id, confirmed=True))
        db.commit()

    with TestClient(app) as client:
        month = client.get("/analytics/monthly-spend", headers=AUTH_HEADERS).json()
        cashflow = client.get("/analytics/cashflow-trend", headers=AUTH_HEADERS).json()
        drilldown = client.get("/transactions", params={"q": "is:spend", "limit": 100}, headers=AUTH_HEADERS).json()

    with SessionLocal() as db:
        view_expense, view_income = db.execute(text("""
            SELECT COALESCE(SUM(expense_amount), 0), COALESCE(SUM(income_amount), 0)
            FROM effective_transactions WHERE date >= '2026-03-01' AND date <= '2026-03-31'
        """)).one()

    # Original March spend is 600. The unresolved candidate remains counted;
    # the pending authorization and confirmed transfer do not.
    assert {row["month"]: row["spend"] for row in month}["2026-03"] == 650.0
    march = {row["month"]: row for row in cashflow}["2026-03"]
    assert (march["expenses"], march["income"], march["net"]) == (650.0, 1050.0, 400.0)
    assert (float(view_expense), float(view_income)) == (650.0, 1050.0)
    ids = {row["plaid_transaction_id"] for row in drilldown["items"]}
    assert "tx-pending" not in ids
    assert "tx-confirmed-out" not in ids
    assert "tx-candidate-out" in ids


def test_category_spend_reflects_rule_apply_outcomes():
    with SessionLocal() as db:
        item = Item(plaid_item_id="i-rule-analytics", access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        account = Account(plaid_account_id="a-rule-analytics", item_id=item.id, name="Rewards Card")
        db.add(account)
        db.flush()
        db.add_all(
            [
                Transaction(
                    plaid_transaction_id="tx-rule-analytics-1",
                    account_id=account.id,
                    item_id=item.id,
                    date=date(2026, 4, 7),
                    amount=8.0,
                    name="Starbucks Downtown",
                    plaid_category_primary="DINING",
                    pending=False,
                ),
                Transaction(
                    plaid_transaction_id="tx-rule-analytics-2",
                    account_id=account.id,
                    item_id=item.id,
                    date=date(2026, 4, 8),
                    amount=20.0,
                    name="Neighborhood Market",
                    plaid_category_primary="GROCERIES",
                    pending=False,
                ),
            ]
        )
        db.commit()

    with TestClient(app) as client:
        create_rule = client.post(
            "/category-rules",
            json={"rank": 1, "enabled": True, "description_regex": "starbucks", "assigned_category": "coffee"},
            headers=AUTH_HEADERS,
        )
        assert create_rule.status_code == 200

        apply_resp = client.post(
            "/category-rules/apply",
            json={"dry_run": False, "scope": {"start_date": "2026-04-01", "end_date": "2026-04-30"}},
            headers=AUTH_HEADERS,
        )
        assert apply_resp.status_code == 200

        analytics = client.get("/analytics/category-spend", headers=AUTH_HEADERS)
        assert analytics.status_code == 200

    by_cat = {row["category"]: row["spend"] for row in analytics.json()}
    assert by_cat["coffee"] == 8.0
    assert by_cat["GROCERIES"] == 20.0
