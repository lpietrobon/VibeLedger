"""CF-07 reporting limits and independent CF-02 accounting oracles."""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.time import utcnow
from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, SyncRun, SyncState, Transaction, TransactionAnnotation
from app.services.accounting import comparison_bounds, reporting_scope
from app.services.security import encrypt_token
from tests.cashflow_fixture import seed_cashflow_ledger
from tests.conftest import AUTH_HEADERS


def add_row(db, key, amount=10, currency="USD", when=date(2024, 2, 10), *, pending=False, raw=None):
    item = db.query(Item).first()
    if item is None:
        item = Item(plaid_item_id="reporting-item", access_token_encrypted=encrypt_token("t"))
        db.add(item)
        db.flush()
    account = Account(plaid_account_id=f"account-{key}", item_id=item.id, name=key, currency=currency)
    db.add(account)
    db.flush()
    tx = Transaction(plaid_transaction_id=key, account_id=account.id, item_id=item.id,
                     date=when, amount=amount, name=key, pending=pending, raw_json=raw)
    db.add(tx)
    db.flush()
    return tx


@pytest.mark.parametrize("as_of,granularity,expected", [
    ("2024-03-15", "monthly", ("2024-03-01", "2024-03-15", "2024-02-01", "2024-02-15")),
    ("2024-03-31", "monthly", ("2024-03-01", "2024-03-31", "2024-02-01", "2024-02-29")),
    ("2025-02-28", "monthly", ("2025-02-01", "2025-02-28", "2025-01-01", "2025-01-31")),
    ("2024-01-02", "monthly", ("2024-01-01", "2024-01-02", "2023-12-01", "2023-12-02")),
    ("2024-02-29", "yearly", ("2024-01-01", "2024-02-29", "2023-01-01", "2023-02-28")),
])
def test_calendar_comparison_bounds(as_of, granularity, expected):
    assert tuple(map(str, comparison_bounds(date.fromisoformat(as_of), granularity))) == expected


def test_cf02_oracle_api_sql_categories_and_all_evidence_pages():
    with SessionLocal() as db:
        seeded = seed_cashflow_ledger(db)
        db.commit()
    with TestClient(app) as client:
        monthly = client.get("/analytics/cashflow-trend", headers=AUTH_HEADERS).json()
        for row in monthly:
            assert {k: row[k] for k in ("income", "expenses", "net")} == seeded["oracle"]["expected"][row["month"]]
        overview = client.get("/analytics/overview", params={"reporting_date": "2024-02-29"}, headers=AUTH_HEADERS).json()
        assert (overview["month_spend"], overview["month_income"], overview["net_cashflow"]) == (-30, 3000, 3030)
        summary = client.get("/analytics/spending-summary", params={"reporting_date": "2024-02-29"}, headers=AUTH_HEADERS).json()
        assert (summary["total"], summary["previous_total"], summary["change"], summary["change_pct"]) == (-30, 225, -255, -113.33)
        yearly = client.get("/analytics/spending-summary", params={"reporting_date": "2024-02-29", "granularity": "yearly"}, headers=AUTH_HEADERS).json()
        assert yearly["total"] == seeded["oracle"]["expected"]["2024-YTD-02-29"]["expenses"]
        assert yearly["reporting"]["previous_period"]["end_date"] == "2023-02-28"
        assert yearly["change"] is None
        bounds = {"start_date": "2024-02-01", "end_date": "2024-02-29"}
        categories = client.get("/analytics/category-spend", params=bounds, headers=AUTH_HEADERS).json()
        assert sum(row["spend"] for row in categories) == -30
        assert any(row["spend"] == -120 for row in categories)
        sankey = client.get("/analytics/cashflow-sankey", params=bounds, headers=AUTH_HEADERS).json()
        assert (sankey["total_spend"], sankey["savings"], sankey["deficit"]) == (-30, 3030, 0)
        assert sankey["sankey_supported"] is False
        assert sum(row["amount"] for row in sankey["negative_categories"]) == -120
        evidence = []
        for offset in range(0, 30, 2):
            page = client.get("/transactions", params={**bounds, "q": "is:spend", "limit": 2, "offset": offset}, headers=AUTH_HEADERS).json()
            evidence.extend(page["items"])
            if len(evidence) >= page["total"]:
                break
        assert sum(row["amount"] for row in evidence) == -30
        assert len(evidence) == 3
    with SessionLocal() as db:
        expense, income = db.execute(text("SELECT SUM(expense_amount), SUM(income_amount) FROM effective_transactions WHERE date BETWEEN '2024-02-01' AND '2024-02-29'")).one()
        assert (expense, income) == (-30, 3000)
        assert db.execute(text("SELECT DISTINCT currency FROM effective_transactions")).scalars().all() == ["USD"]


@pytest.mark.parametrize("currency,status", [(None, "unknown"), ("", "unknown"), ("EUR", "single")])
@pytest.mark.parametrize("path,params", [
    ("monthly-spend", {}), ("category-spend", {}), ("cashflow-trend", {}),
    ("overview", {"reporting_date": "2024-02-29"}),
    ("spending-summary", {"reporting_date": "2024-02-29"}),
    ("cumulative-spend", {"reporting_date": "2024-02-29"}),
    ("cashflow-sankey", {}), ("recurring", {}),
    ("category-movers", {"reporting_date": "2024-02-29"}), ("daily-spend", {"year": 2024}),
])
def test_all_cashflow_consumers_refuse_unknown_and_non_usd(currency, status, path, params):
    with SessionLocal() as db:
        add_row(db, "unsupported", currency=currency)
        db.commit()
    with TestClient(app) as client:
        response = client.get(f"/analytics/{path}", params=params, headers=AUTH_HEADERS)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "unsupported_currency_scope"
    assert detail["currency_status"] == status


def test_currency_scope_mixed_provider_conflict_and_excluded_rows():
    with SessionLocal() as db:
        add_row(db, "usd", currency=" usd ")
        add_row(db, "eur", currency="EUR", when=date(2023, 1, 1))
        add_row(db, "pending", currency=None, pending=True)
        db.commit()
    with TestClient(app) as client:
        response = client.get("/analytics/monthly-spend", headers=AUTH_HEADERS)
        assert response.status_code == 422
        assert response.json()["detail"]["currency_status"] == "mixed"
        response = client.get("/analytics/monthly-spend", params={"start_date": "2024-02-01"}, headers=AUTH_HEADERS)
        assert response.json() == [{"month": "2024-02", "spend": 10}]
    with SessionLocal() as db:
        tx = db.query(Transaction).filter_by(plaid_transaction_id="usd").one()
        tx.raw_json = json.dumps({"iso_currency_code": "EUR"})
        db.commit()
    with TestClient(app) as client:
        response = client.get("/analytics/monthly-spend", params={"start_date": "2024-02-01"}, headers=AUTH_HEADERS)
        assert response.status_code == 422
        assert response.json()["detail"]["currencies"] == ["CONFLICT"]


@pytest.mark.parametrize("raw,expected", [
    ('{"iso_currency_code":"USD"}', 200),
    ('{"unofficial_currency_code":"BTC"}', 422),
    ('not-json', 422),
])
def test_provider_currency_without_account_currency(raw, expected):
    with SessionLocal() as db:
        add_row(db, "provider", currency=None, raw=raw)
        db.commit()
    with TestClient(app) as client:
        assert client.get("/analytics/monthly-spend", headers=AUTH_HEADERS).status_code == expected


def test_prior_currency_is_checked_even_when_current_is_supported():
    with SessionLocal() as db:
        add_row(db, "current")
        add_row(db, "prior", currency="EUR", when=date(2024, 1, 10))
        db.commit()
    with TestClient(app) as client:
        assert client.get("/analytics/spending-summary", params={"reporting_date": "2024-02-29"}, headers=AUTH_HEADERS).status_code == 422


def test_zero_row_sync_does_not_establish_history_or_duplicate_coverage():
    with SessionLocal() as db:
        item = Item(plaid_item_id="empty-history", access_token_encrypted=encrypt_token("t"))
        db.add(item)
        db.flush()
        db.add(SyncState(item_id=item.id, last_success_at=utcnow()))
        db.add(SyncRun(item_id=item.id, status="success", is_historical=True,
                       finished_at=utcnow(), added_count=0))
        db.commit()
    with TestClient(app) as client:
        empty = client.get("/analytics/spending-summary", params={"reporting_date": "2024-02-29"}, headers=AUTH_HEADERS).json()
        assert empty["total"] == 0
        assert empty["reporting"]["currency_status"] == "empty"
        assert empty["change"] is None
        assert empty["reporting"]["comparison_available"] is False
        assert empty["reporting"]["history_coverage"] == "unverified"
        assert empty["reporting"]["duplicate_account_coverage"] == "unverified"


def test_recorded_zero_prior_is_distinct_from_missing_prior_and_negative_denominator():
    with SessionLocal() as db:
        add_row(db, "current", amount=20)
        db.commit()
    with TestClient(app) as client:
        params = {"reporting_date": "2024-02-29"}
        missing = client.get("/analytics/spending-summary", params=params, headers=AUTH_HEADERS).json()
        assert missing["change"] is None
        assert missing["top_driver"] is None
        with SessionLocal() as db:
            refund = add_row(db, "prior-refund", amount=-10, when=date(2024, 1, 10))
            db.add(TransactionAnnotation(transaction_id=refund.id, refund_status="confirmed"))
            db.commit()
        negative = client.get("/analytics/spending-summary", params=params, headers=AUTH_HEADERS).json()
        assert negative["change_pct"] == 300
        with SessionLocal() as db:
            add_row(db, "prior-charge", when=date(2024, 1, 10))
            db.commit()
        zero = client.get("/analytics/spending-summary", params=params, headers=AUTH_HEADERS).json()
        assert zero["reporting"]["comparison_available"] is True
        assert zero["previous_total"] == 0
        assert zero["change"] == 20
        assert zero["change_pct"] is None


def test_reporting_date_not_latest_row_and_same_day_prior_boundary():
    with SessionLocal() as db:
        add_row(db, "current", amount=50, when=date(2024, 3, 2))
        add_row(db, "prior-in-range", amount=20, when=date(2024, 2, 15))
        add_row(db, "prior-too-late", amount=80, when=date(2024, 2, 16))
        add_row(db, "future", amount=999, when=date(2024, 3, 16))
        db.commit()
    with TestClient(app) as client:
        summary = client.get("/analytics/spending-summary", params={"reporting_date": "2024-03-15"}, headers=AUTH_HEADERS).json()
        assert (summary["total"], summary["previous_total"], summary["change_pct"]) == (50, 20, 150)
        assert summary["projection"] == 103.33
        assert summary["reporting"]["current_period"]["end_date"] == "2024-03-15"
        today = client.get("/analytics/overview", headers=AUTH_HEADERS).json()
        assert today["as_of_date"] == str(date.today())


def test_account_balance_currency_guard_is_independent_of_transaction_history():
    with SessionLocal() as db:
        tx = add_row(db, "account", currency="EUR", pending=True)
        account = db.get(Account, tx.account_id)
        account.type = "depository"
        account.current_balance = 100
        db.commit()
    with TestClient(app) as client:
        assert client.get("/analytics/monthly-spend", headers=AUTH_HEADERS).json() == []
        assert client.get("/analytics/accounts-summary", headers=AUTH_HEADERS).status_code == 422
        assert client.get("/analytics/overview", headers=AUTH_HEADERS).status_code == 422
