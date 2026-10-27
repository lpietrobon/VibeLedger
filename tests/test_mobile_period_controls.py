"""Contract for compact period controls: explicit three-window pace, daily cashflow,
and ranked same-day source evidence. All numerical oracles are independent constants.
"""
from datetime import date

from fastapi.testclient import TestClient
from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Transaction, TransactionAnnotation
from tests.conftest import AUTH_HEADERS
from tests.test_mobile_analytics import _seed


def test_overview_short_range_returns_daily_cashflow_without_changing_legacy_monthly_api():
    _seed()
    params = {"start_date": "2020-03-01", "end_date": "2020-03-10"}
    with TestClient(app) as client:
        daily = client.get("/analytics/cashflow-trend", headers=AUTH_HEADERS,
                           params={**params, "granularity": "daily"})
        monthly = client.get("/analytics/cashflow-trend", headers=AUTH_HEADERS, params=params)
    assert daily.status_code == 200, daily.text
    rows = daily.json()
    assert len(rows) == 10
    assert rows[0] == {"month": "2020-03-01", "income": 1200.0,
                       "expenses": 0.0, "net": 1200.0}
    assert rows[4] == {"month": "2020-03-05", "income": 0.0,
                       "expenses": 300.0, "net": -300.0}
    assert rows[5]["expenses"] == 0.0
    assert monthly.json() == [{"month": "2020-03", "income": 1200.0,
                               "expenses": 500.0, "net": 700.0}]


def test_three_historical_comparisons_use_exact_supplied_windows_not_legacy_pace():
    _seed()
    params = {"start_date": "2020-03-01", "end_date": "2020-03-10",
              "compare_start_date": "2020-02-01", "compare_end_date": "2020-02-10",
              "compare2_start_date": "2020-01-01", "compare2_end_date": "2020-01-10",
              "compare3_start_date": "2019-12-01", "compare3_end_date": "2019-12-10"}
    with TestClient(app) as client:
        r = client.get("/analytics/cumulative-spend", headers=AUTH_HEADERS, params=params)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 10
    assert rows[4]["current"] == 300.0
    assert rows[5]["previous1"] == 400.0
    assert rows[9]["current"] == 500.0
    assert rows[9]["previous1"] == 400.0
    assert all(p["previous2"] is None and p["previous3"] is None for p in rows)


def test_no_historical_lines_does_not_affect_spending_summary_first_prior():
    _seed()
    with TestClient(app) as client:
        pace = client.get("/analytics/cumulative-spend", headers=AUTH_HEADERS,
                          params={"start_date": "2020-03-01", "end_date": "2020-03-10"})
        summary = client.get("/analytics/spending-summary", headers=AUTH_HEADERS,
                             params={"start_date": "2020-03-01", "end_date": "2020-03-10",
                                     "compare_start_date": "2020-02-01", "compare_end_date": "2020-02-10"})
    assert pace.status_code == 200
    assert all(p["previous1"] is None for p in pace.json())
    assert summary.json()["previous_total"] == 400.0


def test_selected_day_returns_signed_top_five_and_full_net_day_parity():
    _seed()
    with SessionLocal() as db:
        account = db.query(Account).first()
        for i, amount in enumerate((200, 150, 100, 75, 50, 25, -100)):
            row = Transaction(
                plaid_transaction_id="rank-%d" % i,
                account_id=account.id, item_id=account.item_id,
                date=date(2020, 3, 5), amount=amount,
                name="Merchant %d" % i, merchant_name="Merchant %d" % i,
                plaid_category_primary="FOOD_AND_DRINK", pending=False,
            )
            db.add(row)
            db.flush()
            if amount < 0:
                db.add(TransactionAnnotation(transaction_id=row.id,
                                             refund_status="confirmed", user_category="FOOD/OTHER"))
        db.commit()
    with TestClient(app) as client:
        detail = client.get("/analytics/spending-day", headers=AUTH_HEADERS,
                            params={"selected_date": "2020-03-05"})
        timeline = client.get("/analytics/timeline-spikes", headers=AUTH_HEADERS,
                              params={"start_date": "2020-03-05", "end_date": "2020-03-05"})
        all_rows = client.get("/transactions", headers=AUTH_HEADERS,
                              params={"start_date": "2020-03-05", "end_date": "2020-03-05",
                                      "q": "is:spend", "limit": 100})
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["total"] == 800.0
    assert body["transaction_count"] == 8
    assert [row["amount"] for row in body["items"]] == [300, 200, 150, 100, 75]
    assert [row["percent_of_day"] for row in body["items"]] == [37.5, 25.0, 18.8, 12.5, 9.4]
    assert body["items"][-1]["cumulative_percent"] == 103.1  # refund offsets
    assert timeline.json()["days"][0]["amount"] == 800.0
    assert sum(row["amount"] for row in all_rows.json()["items"]) == 800.0


def test_invalid_comparison_pairs_are_rejected():
    _seed()
    with TestClient(app) as client:
        for extra in (
            {"compare2_start_date": "2020-02-01"},
            {"compare2_start_date": "2020-02-01", "compare2_end_date": "2020-02-10"},
            {"compare3_start_date": "2020-02-01", "compare3_end_date": "2020-02-10"},
        ):
            response = client.get("/analytics/cumulative-spend", headers=AUTH_HEADERS,
                params={"start_date": "2020-03-01", "end_date": "2020-03-10", **extra})
            assert response.status_code == 422, (extra, response.text)
