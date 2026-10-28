"""Explicit selected windows and source evidence parity (TIME-04).

Fixed fixture dates and independent arithmetic are intentional.
"""
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import AUTH_HEADERS
from tests.test_mobile_analytics import _seed


def test_custom_range_without_comparison_is_not_a_fake_change():
    _seed()
    with TestClient(app) as client:
        response = client.get("/analytics/spending-summary", headers=AUTH_HEADERS, params={
            "start_date": "2020-03-05", "end_date": "2020-03-10",
        })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 500.0
    assert data["previous_total"] == 0.0
    assert data["change"] is None
    assert data["projection"] == 500.0
    assert data["reporting"]["comparison_available"] is False


def test_custom_comparison_date_alignment_and_activity_parity():
    _seed()
    dates = {"start_date": "2020-03-05", "end_date": "2020-03-10",
             "compare_start_date": "2020-02-01", "compare_end_date": "2020-02-28"}
    with TestClient(app) as client:
        summary = client.get("/analytics/spending-summary", headers=AUTH_HEADERS, params=dates)
        overview = client.get("/analytics/overview", headers=AUTH_HEADERS, params=dates)
        pace = client.get("/analytics/cumulative-spend", headers=AUTH_HEADERS, params=dates)
        activity = client.get("/transactions", headers=AUTH_HEADERS, params={
            "start_date": "2020-03-05", "end_date": "2020-03-10", "q": "is:spend", "limit": 100})
    assert all(r.status_code == 200 for r in (summary, overview, pace, activity))
    assert summary.json()["total"] == 500.0
    assert summary.json()["previous_total"] == 400.0
    assert summary.json()["change"] == 100.0
    assert summary.json()["reporting"]["current_period"]["start_date"] == "2020-03-05"
    assert overview.json()["month_spend"] == 500.0
    assert overview.json()["previous_month_spend"] == 400.0
    assert len(pace.json()) == 6
    assert pace.json()[0]["date"] == "2020-03-05"
    assert pace.json()[-1]["current"] == 500.0
    assert pace.json()[-1]["previous1"] == 400.0
    assert sorted(row["amount"] for row in activity.json()["items"]) == [200.0, 300.0]


def test_timeline_days_equal_filtered_posted_activity():
    _seed()
    with TestClient(app) as client:
        response = client.get("/analytics/timeline-spikes", headers=AUTH_HEADERS,
                              params={"start_date": "2020-03-01", "end_date": "2020-03-10"})
        activity = client.get("/transactions", headers=AUTH_HEADERS,
                              params={"start_date": "2020-03-01", "end_date": "2020-03-10",
                                      "q": "is:spend", "limit": 100})
    assert response.status_code == 200, response.text
    assert activity.status_code == 200
    by_day = {row["date"]: row["amount"] for row in response.json()["days"]}
    assert by_day["2020-03-05"] == 300.0
    assert by_day["2020-03-10"] == 200.0
    assert by_day["2020-03-06"] == 0.0
    assert sum(by_day.values()) == sum(row["amount"] for row in activity.json()["items"])
    assert response.json()["spikes"] == []  # Insufficient baseline, not presumed zero


def test_invalid_partial_or_reversed_windows_rejected():
    _seed()
    cases = [{"start_date": "2020-03-01"},
             {"start_date": "2020-03-10", "end_date": "2020-03-01"},
             {"start_date": "2020-03-01", "end_date": "2020-03-10",
              "compare_start_date": "2020-02-01"}]
    with TestClient(app) as client:
        for params in cases:
            response = client.get("/analytics/spending-summary", headers=AUTH_HEADERS, params=params)
            assert response.status_code == 422, (params, response.text)
