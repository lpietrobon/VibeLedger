"""Independent TIME-04 literal ledger parity; no production date helpers as oracle."""
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.models import Transaction, DuplicateCorrection
from tests.conftest import AUTH_HEADERS
from tests.category_drilldown_fixture import seed_category_drilldown_ledger

BOUNDS = {"start_date": "2032-04-02", "end_date": "2032-04-09"}


def seed():
    with SessionLocal() as db:
        seeded = seed_category_drilldown_ledger(db)
        canonical = db.get(Transaction, seeded["transaction_ids"]["food-charge-1"])
        for i in range(502):
            row = Transaction(plaid_transaction_id=f"time04-{i}", account_id=canonical.account_id,
                item_id=canonical.item_id, date=date(2032, 4, 2), amount=40 if i == 501 else 1,
                name=f"TIME04-{i}", pending=False, plaid_category_primary="FOOD_AND_DRINK")
            db.add(row)
            db.flush()
            if i == 501:
                db.add(DuplicateCorrection(canonical_transaction_id=canonical.id,
                    duplicate_transaction_id=row.id, status="active"))
        db.commit()


def get(client, path, params):
    response = client.get(path, params=params, headers=AUTH_HEADERS)
    assert response.status_code == 200, response.text
    return response.json()


def test_every_selected_aggregate_equals_complete_paginated_posted_evidence():
    seed()
    # Literal: 40+25-10+12+20+17 + 501 one-dollar rows = 605.
    # Pending 999, confirmed transfer 30, and duplicate 40 contribute zero.
    with TestClient(app) as client:
        first = get(client, "/transactions", {**BOUNDS, "q": "is:spend", "limit": 500})
        second = get(client, "/transactions", {**BOUNDS, "q": "is:spend", "limit": 500, "offset": 500})
        assert first["total"] == 507
        assert len(first["items"]) == 500 and len(second["items"]) == 7
        rows = first["items"] + second["items"]
        assert len({r["id"] for r in rows}) == 507
        assert sum(r["amount"] for r in rows) == 605
        overview = get(client, "/analytics/overview", BOUNDS)
        summary = get(client, "/analytics/spending-summary", BOUNDS)
        categories = get(client, "/analytics/category-spend", BOUNDS)
        trend = get(client, "/analytics/cashflow-trend", BOUNDS)
        timeline = get(client, "/analytics/timeline-spikes", BOUNDS)
        sankey = get(client, "/analytics/cashflow-sankey", BOUNDS)
        cumulative = get(client, "/analytics/cumulative-spend", BOUNDS)
        assert overview["month_spend"] == summary["total"] == sankey["total_spend"] == 605
        assert sum(r["spend"] for r in categories) == 605
        assert sum(r["expenses"] for r in trend) == 605
        assert sum(r["amount"] for r in timeline["days"]) == 605
        assert timeline["days"][0]["date"] == "2032-04-02"
        assert timeline["days"][-1]["date"] == "2032-04-09"
        assert cumulative[-1]["current"] == 605
        assert summary["reporting"]["comparison_available"] is False
        assert summary["change"] is None


def test_unavailable_comparable_history_is_not_zero_percent_growth():
    seed()
    with TestClient(app) as client:
        for path in ("/analytics/spending-summary", "/analytics/overview"):
            body = get(client, path, {**BOUNDS, "compare_start_date": "2031-04-02", "compare_end_date": "2031-04-09"})
            assert body["reporting"]["comparison_available"] is False
            assert body["reporting"]["comparison_qualification"]
        empty = get(client, "/analytics/spending-summary", {"start_date": "2040-01-01", "end_date": "2040-01-05"})
        assert empty["total"] == 0
        assert empty["change_pct"] is None
