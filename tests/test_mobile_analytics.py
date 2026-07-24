"""Contract tests for the consolidated analytics endpoints that back the
mobile (React) app: /analytics/overview, /analytics/spending-summary,
/analytics/cumulative-spend, and q= search on /transactions.

Data is seeded in 2020 so the "current month" projection branch never triggers
regardless of when the suite runs, keeping assertions deterministic.
"""
from datetime import date

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def _seed():
    with SessionLocal() as db:
        item = Item(plaid_item_id="i-mob", access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        account = Account(plaid_account_id="a-mob", item_id=item.id, name="Checking")
        db.add(account)
        db.flush()

        rows = [
            (date(2020, 2, 1), -1000.0, "Paycheck", "INCOME"),
            (date(2020, 2, 6), 400.0, "Groceries", "FOOD_AND_DRINK"),
            (date(2020, 3, 1), -1200.0, "Paycheck", "INCOME"),
            (date(2020, 3, 5), 300.0, "Groceries", "FOOD_AND_DRINK"),
            (date(2020, 3, 10), 200.0, "Coffee", "FOOD_AND_DRINK"),
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
                    merchant_name=name,
                    plaid_category_primary=cat,
                    pending=False,
                )
            )
        db.commit()


def test_overview_kpis_and_needs_attention():
    _seed()
    with TestClient(app) as client:
        r = client.get("/analytics/overview", headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["as_of_date"] == "2020-03-10"
    assert body["month_spend"] == 500.0
    assert body["previous_month_spend"] == 400.0
    assert body["month_income"] == 1200.0
    assert body["net_cashflow"] == 700.0
    na = body["needs_attention"]
    assert na["unreviewed_transactions"] == 5  # nothing reviewed yet
    assert na["uncategorized_transactions"] == 0  # all map to friendly categories
    assert na["likely_refunds"] == 0
    assert na["transfer_pairs_pending"] == 0


def test_spending_summary_monthly():
    _seed()
    with TestClient(app) as client:
        r = client.get("/analytics/spending-summary", headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 500.0
    assert body["previous_total"] == 400.0
    assert body["change"] == 100.0
    assert body["change_pct"] == 25.0
    assert body["projection"] == 500.0  # 2020-03 is not the live month
    assert body["top_driver"]["category"] == "FOOD/OTHER"
    assert body["top_driver"]["amount"] == 100.0
    comp = {row["category"]: row for row in body["category_comparison"]}
    assert comp["FOOD/OTHER"]["current"] == 500.0
    assert comp["FOOD/OTHER"]["previous"] == 400.0


def test_spending_summary_yearly():
    _seed()
    with TestClient(app) as client:
        r = client.get("/analytics/spending-summary", params={"granularity": "yearly"}, headers=AUTH_HEADERS)
    body = r.json()
    assert body["period_label"] == "2020 YTD"
    assert body["total"] == 900.0
    assert body["previous_total"] == 0.0
    assert body["change_pct"] is None  # no prior-year baseline


def test_cumulative_spend_monthly():
    _seed()
    with TestClient(app) as client:
        r = client.get("/analytics/cumulative-spend", headers=AUTH_HEADERS)
    rows = r.json()
    assert len(rows) == 31  # March
    by_x = {row["x"]: row for row in rows}
    assert by_x[5]["current"] == 300.0
    assert by_x[10]["current"] == 500.0
    assert by_x[11]["current"] is None  # past the last charge day
    assert by_x[6]["previous1"] == 400.0  # February
    assert by_x[1]["previous2"] is None  # no data two months back


def test_transactions_search_query():
    _seed()
    with TestClient(app) as client:
        coffee = client.get("/transactions", params={"q": "coffee"}, headers=AUTH_HEADERS).json()
        groceries = client.get("/transactions", params={"q": "groceries"}, headers=AUTH_HEADERS).json()
        by_cat = client.get("/transactions", params={"q": "food/other"}, headers=AUTH_HEADERS).json()
    assert [t["name"] for t in coffee["items"]] == ["Coffee"]
    assert coffee["total"] == 1
    assert sorted(t["name"] for t in groceries["items"]) == ["Groceries", "Groceries"]
    assert by_cat["total"] == 3  # all three FOOD_AND_DRINK rows map to FOOD/OTHER
