"""INV-07 frozen RED contract for M3 investment visibility (synthetic only)."""
from datetime import date
from tests.test_investment_ingestion import Provider, seed, service, START, END
from app.db.session import SessionLocal
from app.services.investment_sync import investment_summary


def test_summary_exposes_filtered_holdings_history_and_qualifications():
    with SessionLocal() as db:
        item_id = seed(db)
        service(Provider()).sync_item(db, item_id, START, END)
        result = investment_summary(db, start_date=START, end_date=END, account_ids=None, tax_filter="all")
    assert result["currency"] == "USD"
    assert result["as_of"]["provenance"] == "observed"
    assert result["effective_range"] == {"start_date": "2026-01-01", "end_date": "2026-01-31"}
    assert result["total_value"] == 1250
    assert result["holdings"][0]["security_id"] == "fund"
    assert result["history"][0]["value"] == 1250
    assert result["gain"] is None


def test_empty_or_missing_data_is_absent_not_zero():
    with SessionLocal() as db:
        result = investment_summary(db, start_date=START, end_date=END, account_ids=None, tax_filter="all")
    assert result["total_value"] is None
    assert result["state"] == "not_connected"


def test_endpoint_accepts_exact_bounds_and_account_scope():
    from fastapi.testclient import TestClient
    from app.main import app
    from tests.conftest import AUTH_HEADERS
    with TestClient(app) as client:
        response = client.get("/investments/summary", params={"start_date":"2026-01-01", "end_date":"2026-01-31", "tax_filter":"roth", "account_ids": 999}, headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert response.json()["effective_range"] == {"start_date":"2026-01-01", "end_date":"2026-01-31"}
