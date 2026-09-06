"""Tests for the Insights page endpoints: /analytics/cashflow-sankey,
/analytics/category-movers, /analytics/daily-spend."""
from datetime import date

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction, TransactionAnnotation
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def _seed_item_and_account(item_id: str, account_id: str, name: str = "Checking"):
    with SessionLocal() as db:
        item = Item(plaid_item_id=item_id, access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        account = Account(plaid_account_id=account_id, item_id=item.id, name=name, currency="USD")
        db.add(account)
        db.flush()
        db.commit()
        return item.id, account.id


def _add_txn(account_id: int, item_id: int, d: date, amount: float, name: str, category: str):
    with SessionLocal() as db:
        db.add(
            Transaction(
                plaid_transaction_id=f"tx-{account_id}-{d}-{name}-{amount}",
                account_id=account_id,
                item_id=item_id,
                date=d,
                amount=amount,
                name=name,
                plaid_category_primary=category,
                pending=False,
            )
        )
        db.commit()


def _seed_sankey_ledger():
    item_id, account_id = _seed_item_and_account("i-sankey", "a-sankey")
    rows = [
        (date(2026, 3, 1), -1000.0, "Paycheck", "INCOME"),
        (date(2026, 3, 5), 300.0, "Groceries", "FOOD/GROCERIES"),
        (date(2026, 3, 6), 100.0, "Restaurant", "FOOD/DINING"),
        (date(2026, 3, 10), 500.0, "Rent", "RENT_AND_UTILITIES"),
    ]
    for d, amt, name, cat in rows:
        _add_txn(account_id, item_id, d, amt, name, cat)
    return item_id, account_id


def test_cashflow_sankey_buckets_and_categories():
    _seed_sankey_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/cashflow-sankey", headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["income"] == 1000.0
    assert body["total_spend"] == 900.0
    assert body["savings"] == 100.0
    assert body["deficit"] == 0.0

    buckets = {b["bucket"]: b for b in body["buckets"]}
    assert buckets["FOOD"]["amount"] == 400.0
    assert buckets["HOUSING"]["amount"] == 500.0
    food_categories = {c["category"]: c["amount"] for c in buckets["FOOD"]["categories"]}
    assert food_categories["FOOD/GROCERIES"] == 300.0
    assert food_categories["FOOD/DINING"] == 100.0


def test_cashflow_sankey_deficit_when_spend_exceeds_income():
    item_id, account_id = _seed_item_and_account("i-deficit", "a-deficit")
    _add_txn(account_id, item_id, date(2026, 3, 1), -100.0, "Paycheck", "INCOME")
    _add_txn(account_id, item_id, date(2026, 3, 5), 900.0, "Rent", "RENT_AND_UTILITIES")

    with TestClient(app) as client:
        r = client.get("/analytics/cashflow-sankey", headers=AUTH_HEADERS)
    body = r.json()
    assert body["income"] == 100.0
    assert body["total_spend"] == 900.0
    assert body["savings"] == 0.0
    assert body["deficit"] == 800.0


def test_cashflow_sankey_refund_nets_against_expense_not_income():
    item_id, account_id = _seed_sankey_ledger()
    with SessionLocal() as db:
        txn = Transaction(
            plaid_transaction_id="tx-refund-sankey",
            account_id=account_id,
            item_id=item_id,
            date=date(2026, 3, 15),
            amount=-100.0,
            name="Restaurant refund",
            plaid_category_primary="FOOD_AND_DRINK",
            pending=False,
        )
        db.add(txn)
        db.flush()
        db.add(TransactionAnnotation(transaction_id=txn.id, refund_status="likely"))
        db.commit()

    with TestClient(app) as client:
        r = client.get("/analytics/cashflow-sankey", headers=AUTH_HEADERS)
    body = r.json()
    assert body["income"] == 1000.0  # refund does not count as income
    buckets = {b["bucket"]: b for b in body["buckets"]}
    assert buckets["FOOD"]["amount"] == 300.0  # 400 - 100 refund


def test_cashflow_sankey_date_filter():
    _seed_sankey_ledger()
    with TestClient(app) as client:
        r = client.get(
            "/analytics/cashflow-sankey",
            params={"start_date": "2026-03-06", "end_date": "2026-03-31"},
            headers=AUTH_HEADERS,
        )
    body = r.json()
    assert body["income"] == 0.0  # paycheck on 3/1 excluded
    assert body["total_spend"] == 600.0  # restaurant (100) + rent (500)


def test_cashflow_sankey_ignores_pending_activity():
    item_id, account_id = _seed_sankey_ledger()
    with SessionLocal() as db:
        db.add_all(
            [
                Transaction(
                    plaid_transaction_id="tx-pending-sankey-spend",
                    account_id=account_id,
                    item_id=item_id,
                    date=date(2026, 3, 20),
                    amount=250.0,
                    name="Pending purchase",
                    pending=True,
                ),
                Transaction(
                    plaid_transaction_id="tx-pending-sankey-income",
                    account_id=account_id,
                    item_id=item_id,
                    date=date(2026, 3, 20),
                    amount=-500.0,
                    name="Pending deposit",
                    pending=True,
                ),
            ]
        )
        db.commit()

    with TestClient(app) as client:
        body = client.get("/analytics/cashflow-sankey", headers=AUTH_HEADERS).json()
    assert body["income"] == 1000.0
    assert body["total_spend"] == 900.0


def _seed_movers_ledger():
    item_id, account_id = _seed_item_and_account("i-movers", "a-movers")
    rows = [
        (date(2026, 5, 5), 200.0, "Groceries May", "FOOD_AND_DRINK"),
        (date(2026, 5, 6), 50.0, "Gas May", "TRANSPORTATION"),
        (date(2026, 6, 5), 350.0, "Groceries June", "FOOD_AND_DRINK"),
        (date(2026, 6, 6), 50.0, "Gas June", "TRANSPORTATION"),
        (date(2026, 6, 7), 80.0, "New subscription", "SUBSCRIPTIONS"),
    ]
    for d, amt, name, cat in rows:
        _add_txn(account_id, item_id, d, amt, name, cat)


def test_category_movers_defaults_to_latest_month():
    _seed_movers_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/category-movers", headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["month"] == "2026-06"
    assert body["previous_month"] == "2026-05"
    by_cat = {row["category"]: row for row in body["items"]}
    assert by_cat["FOOD/OTHER"]["current"] == 350.0
    assert by_cat["FOOD/OTHER"]["previous"] == 200.0
    assert by_cat["FOOD/OTHER"]["change"] == 150.0
    assert by_cat["TRANSPORT/OTHER"]["change"] == 0.0
    assert by_cat["SUBSCRIPTIONS"]["previous"] == 0.0
    assert by_cat["SUBSCRIPTIONS"]["change"] == 80.0


def test_category_movers_sorted_by_absolute_change_desc():
    _seed_movers_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/category-movers", headers=AUTH_HEADERS)
    items = r.json()["items"]
    changes = [abs(row["change"]) for row in items]
    assert changes == sorted(changes, reverse=True)
    assert items[0]["category"] == "FOOD/OTHER"


def test_category_movers_respects_limit():
    _seed_movers_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/category-movers", params={"limit": 1}, headers=AUTH_HEADERS)
    assert len(r.json()["items"]) == 1


def test_category_movers_explicit_month():
    _seed_movers_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/category-movers", params={"month": "2026-05"}, headers=AUTH_HEADERS)
    body = r.json()
    assert body["month"] == "2026-05"
    assert body["previous_month"] == "2026-04"
    by_cat = {row["category"]: row for row in body["items"]}
    assert by_cat["FOOD/OTHER"]["current"] == 200.0
    assert by_cat["FOOD/OTHER"]["previous"] == 0.0


def _seed_daily_ledger():
    item_id, account_id = _seed_item_and_account("i-daily", "a-daily")
    rows = [
        (date(2026, 1, 1), 25.0, "New Year snacks", "FOOD_AND_DRINK"),
        (date(2026, 1, 1), 15.0, "Coffee", "FOOD_AND_DRINK"),
        (date(2026, 3, 15), 200.0, "Rent", "RENT_AND_UTILITIES"),
        (date(2025, 12, 31), 999.0, "Last year", "SHOPS"),
    ]
    for d, amt, name, cat in rows:
        _add_txn(account_id, item_id, d, amt, name, cat)


def test_daily_spend_totals_and_year_range():
    _seed_daily_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/daily-spend", params={"year": 2026}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == 2026
    assert len(body["days"]) == 365  # 2026 is not a leap year
    by_date = {row["date"]: row["amount"] for row in body["days"]}
    assert by_date["2026-01-01"] == 40.0
    assert by_date["2026-03-15"] == 200.0
    assert by_date["2026-01-02"] == 0.0
    assert "2025-12-31" not in by_date


def test_daily_spend_available_years_and_default_year():
    _seed_daily_ledger()
    with TestClient(app) as client:
        r = client.get("/analytics/daily-spend", headers=AUTH_HEADERS)
    body = r.json()
    assert body["year"] == 2026  # latest transaction year
    assert set(body["available_years"]) == {2025, 2026}
    assert body["available_years"] == sorted(body["available_years"], reverse=True)


def test_daily_spend_excludes_transfers():
    item_id, account_id = _seed_item_and_account("i-daily-xfer", "a-daily-xfer-out")
    item_id2, account_id2 = _seed_item_and_account("i-daily-xfer2", "a-daily-xfer-in", name="Savings")
    with SessionLocal() as db:
        out_txn = Transaction(
            plaid_transaction_id="tx-xfer-out",
            account_id=account_id,
            item_id=item_id,
            date=date(2026, 2, 1),
            amount=300.0,
            name="Transfer to savings",
            pending=False,
        )
        in_txn = Transaction(
            plaid_transaction_id="tx-xfer-in",
            account_id=account_id2,
            item_id=item_id2,
            date=date(2026, 2, 1),
            amount=-300.0,
            name="Transfer from checking",
            pending=False,
        )
        db.add_all([out_txn, in_txn])
        db.commit()
        out_id, in_id = out_txn.id, in_txn.id

    with TestClient(app) as client:
        pair = client.post(
            "/transfers",
            json={"txn_a_id": out_id, "txn_b_id": in_id},
            headers=AUTH_HEADERS,
        )
        assert pair.status_code == 200
        r = client.get("/analytics/daily-spend", params={"year": 2026}, headers=AUTH_HEADERS)
    by_date = {row["date"]: row["amount"] for row in r.json()["days"]}
    assert by_date["2026-02-01"] == 0.0


def test_pending_rows_do_not_choose_or_contribute_to_analytics_periods():
    item_id, account_id = _seed_item_and_account("i-pending-period", "a-pending-period")
    _add_txn(account_id, item_id, date(2026, 3, 15), 240.0, "Posted purchase", "FOOD_AND_DRINK")
    with SessionLocal() as db:
        db.add(
            Transaction(
                plaid_transaction_id="tx-pending-future",
                account_id=account_id,
                item_id=item_id,
                date=date(2027, 1, 1),
                amount=999.0,
                name="Pending future purchase",
                pending=True,
            )
        )
        db.commit()

    with TestClient(app) as client:
        daily = client.get("/analytics/daily-spend", headers=AUTH_HEADERS).json()
        movers = client.get("/analytics/category-movers", headers=AUTH_HEADERS).json()
        sankey = client.get("/analytics/cashflow-sankey", headers=AUTH_HEADERS).json()

    assert daily["year"] == 2026
    assert movers["month"] == "2026-03"
    assert sankey["total_spend"] == 240.0
