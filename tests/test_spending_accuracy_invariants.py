"""Independent monetary oracle for shared spending analytics.

Expected cents and eligible row names are literal, not calculated by the API.
Include: posted income, matched refund, candidate and confirmed transfers,
pending rows, duplicate correction, multi-category spend and negative net days.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import (
    Account, DuplicateCorrection, Item, Transaction,
    TransactionAnnotation, TransferPair,
)
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


CURRENT = {"start_date": "2026-10-04", "end_date": "2026-10-07"}
PRIOR = {"compare_start_date": "2026-09-04", "compare_end_date": "2026-09-07"}
DAYS = {"2026-10-04": 100.0, "2026-10-05": 35.0,
        "2026-10-06": 100.0, "2026-10-07": -35.0}
CATEGORY_ORACLE = {"FOOD/OTHER": 65.0, "TRANSPORT/OTHER": 95.0, "SHOPPING": 40.0}
# Seven actual, eligible posted spend rows; even confirmed refunds count negatively.
INCLUDED = {"groceries", "refund20", "transit", "candidate-out",
            "market-canonical", "snack", "refund50"}
EXCLUDED = {"salary", "candidate-in", "confirmed-out", "confirmed-in",
            "pending", "market-duplicate", "outside-before", "outside-after"}


@pytest.fixture
def ledger():
    with SessionLocal() as db:
        item = Item(plaid_item_id="accuracy-ledger", access_token_encrypted=encrypt_token("audit"), status="active")
        db.add(item)
        db.flush()
        account = Account(plaid_account_id="accuracy-checking", item_id=item.id,
                          name="Checking", currency="USD", type="depository")
        db.add(account)
        db.flush()
        # (logical id, day, signed dollars, effective category, pending, refund)
        specs = [
            ("prior-food-1", "2026-09-04", "50.00", "FOOD/OTHER", False, False),
            ("prior-food-2", "2026-09-05", "80.00", "FOOD/OTHER", False, False),
            ("prior-food-3", "2026-09-06", "20.00", "FOOD/OTHER", False, False),
            ("outside-before", "2026-10-03", "999.00", "SHOPPING", False, False),
            ("groceries", "2026-10-04", "120.00", "FOOD/OTHER", False, False),
            ("refund20", "2026-10-04", "-20.00", "FOOD/OTHER", False, True),
            ("transit", "2026-10-05", "35.00", "TRANSPORT/OTHER", False, False),
            ("confirmed-out", "2026-10-05", "200.00", "TRANSPORT/OTHER", False, False),
            ("confirmed-in", "2026-10-05", "-200.00", "INCOME", False, False),
            ("pending", "2026-10-05", "500.00", "SHOPPING", True, False),
            ("candidate-out", "2026-10-06", "60.00", "TRANSPORT/OTHER", False, False),
            ("candidate-in", "2026-10-06", "-60.00", "INCOME", False, False),
            ("market-canonical", "2026-10-06", "40.00", "SHOPPING", False, False),
            ("market-duplicate", "2026-10-06", "40.00", "SHOPPING", False, False),
            ("snack", "2026-10-07", "15.00", "FOOD/OTHER", False, False),
            ("refund50", "2026-10-07", "-50.00", "FOOD/OTHER", False, True),
            ("salary", "2026-10-07", "-1000.00", "INCOME", False, False),
            ("outside-after", "2026-10-08", "888.00", "SHOPPING", False, False),
        ]
        rows = {}
        for key, txn_day, money, cat, pending, refund in specs:
            transaction = Transaction(
                plaid_transaction_id="audit-" + key, item_id=item.id, account_id=account.id,
                date=date.fromisoformat(txn_day), amount=Decimal(money), name=key,
                merchant_name=key, pending=pending, plaid_category_primary=cat,
            )
            db.add(transaction)
            db.flush()
            rows[key] = transaction
            if cat != "INCOME" or refund:
                db.add(TransactionAnnotation(transaction_id=transaction.id,
                                             user_category=cat,
                                             refund_status="confirmed" if refund else None))
        db.add(TransferPair(txn_out_id=rows["confirmed-out"].id, txn_in_id=rows["confirmed-in"].id, confirmed=True))
        db.add(TransferPair(txn_out_id=rows["candidate-out"].id, txn_in_id=rows["candidate-in"].id, confirmed=False))
        db.add(DuplicateCorrection(
            canonical_transaction_id=rows["market-canonical"].id,
            duplicate_transaction_id=rows["market-duplicate"].id, status="active",
            evidence_json="{}",
        ))
        db.commit()
        return {k: v.id for k, v in rows.items()}


def get(client, endpoint, params):
    response = client.get(endpoint, params=params, headers=AUTH_HEADERS)
    assert response.status_code == 200, (endpoint, response.status_code, response.text)
    return response.json()


def all_spending_rows(client):
    """Traverse every page: displaying the first 500 rows isn't proof of parity."""
    offset, result = 0, []
    while True:
        body = get(client, "/transactions", {**CURRENT, "q": "is:spend",
                                             "limit": 2, "offset": offset})
        result.extend(body["items"])
        offset += len(body["items"])
        if offset == body["total"]:
            return result
        assert body["items"], "Pagination must advance"


def test_independent_ledger_reconciles_all_chart_views_and_complete_evidence(ledger):
    with TestClient(app) as client:
        summary = get(client, "/analytics/spending-summary", {**CURRENT, **PRIOR})
        overview = get(client, "/analytics/overview", {**CURRENT, **PRIOR})
        category = get(client, "/analytics/category-spend", CURRENT)
        timeline = get(client, "/analytics/timeline-spikes", CURRENT)
        cumulative = get(client, "/analytics/cumulative-spend", {**CURRENT, **PRIOR})
        sankey = get(client, "/analytics/cashflow-sankey", CURRENT)
        rows = all_spending_rows(client)

    assert {row["name"] for row in rows} == INCLUDED
    assert not ({row["name"] for row in rows} & EXCLUDED)
    assert round(sum(row["amount"] for row in rows), 2) == 200.0
    assert summary["total"] == 200.0
    assert summary["previous_total"] == 150.0
    assert summary["change"] == 50.0
    assert overview["month_spend"] == 200.0
    assert overview["previous_month_spend"] == 150.0
    assert {r["category"]: r["spend"] for r in category if r["spend"]} == CATEGORY_ORACLE
    assert sankey["total_spend"] == 200.0
    assert {p["date"]: p["amount"] for p in timeline["days"]} == DAYS

    assert [p["current"] for p in cumulative] == [100.0, 135.0, 235.0, 200.0]
    assert cumulative[-1]["current"] == summary["total"]
    assert [p["previous1"] for p in cumulative] == [50.0, 130.0, 150.0, 150.0]
    for date_iso, amount in DAYS.items():
        assert round(sum(row["amount"] for row in rows if row["date"] == date_iso), 2) == amount
    assert sum(DAYS.values()) == summary["total"]


def test_no_comparison_means_no_change_even_with_prior_history(ledger):
    with TestClient(app) as client:
        summary = get(client, "/analytics/spending-summary", CURRENT)
    assert summary["total"] == 200.0
    assert summary["change"] is None
    assert summary["change_pct"] is None
    assert summary["reporting"]["comparison_available"] is False


def test_unequal_calendar_comparison_is_disclosed_in_reporting_metadata(ledger):
    # March 29–31 are three days; Feb 28 is only one day.
    # It is legitimate to map calendar dates, but not to silently imply
    # an equal-length apples-to-apples comparison.
    with TestClient(app) as client:
        body = get(client, "/analytics/spending-summary", {
            "start_date": "2026-03-29", "end_date": "2026-03-31",
            "compare_start_date": "2026-02-28", "compare_end_date": "2026-02-28",
        })
    message = body["reporting"]["comparison_qualification"].lower()
    assert "3" in message and "1" in message
    assert "day" in message and ("unequal" in message or "different" in message)


def test_cumulative_negative_refunds_can_decrease_a_total(ledger):
    with TestClient(app) as client:
        points = get(client, "/analytics/cumulative-spend", CURRENT)
    assert [p["current"] for p in points] == [100.0, 135.0, 235.0, 200.0]
    assert points[-1]["current"] < points[-2]["current"]
