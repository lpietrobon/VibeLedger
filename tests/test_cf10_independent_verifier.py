"""CF-10 independent accounting verifier.

Expected values in this file are deliberately literal and are not produced by
the application's accounting helpers.  The tests compare aggregate responses,
category totals, and paginated transaction evidence for the same synthetic
ledger and then exercise changes that are easy to get wrong.
"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Transaction, TransferPair
from tests.cashflow_fixture import seed_cashflow_ledger
from tests.conftest import AUTH_HEADERS


def _add_transaction(db, seeded, key, account_key, amount, when, *, pending=False):
    tx = Transaction(
        plaid_transaction_id=f"cf10-{key}",
        account_id=seeded["account_ids"][account_key],
        item_id=seeded["item_id"],
        date=when,
        amount=Decimal(str(amount)),
        name=key,
        merchant_name=key,
        plaid_category_primary="TEST",
        pending=pending,
    )
    db.add(tx)
    db.flush()
    return tx


def test_independent_oracle_matches_aggregates_categories_and_all_evidence_pages():
    with SessionLocal() as db:
        seeded = seed_cashflow_ledger(db)
        db.commit()

    # Independently derived from the posted event list: internal pairs cancel,
    # pending activity is ignored, and the February refund nets against spend.
    expected = {
        "2024-01": {"income": 3040, "expenses": 225, "net": 2815},
        "2024-02": {"income": 3000, "expenses": -30, "net": 3030},
    }
    with TestClient(app) as client:
        trend = client.get("/analytics/cashflow-trend", headers=AUTH_HEADERS)
        assert trend.status_code == 200
        observed = {row["month"]: row for row in trend.json()}
        for month, values in expected.items():
            assert {key: observed[month][key] for key in values} == values

        summary = client.get(
            "/analytics/spending-summary",
            params={"reporting_date": "2024-02-29"},
            headers=AUTH_HEADERS,
        )
        assert summary.status_code == 200
        assert (summary.json()["total"], summary.json()["previous_total"], summary.json()["change"]) == (-30, 225, -255)

        categories = client.get(
            "/analytics/category-spend",
            params={"start_date": "2024-02-01", "end_date": "2024-02-29"},
            headers=AUTH_HEADERS,
        )
        assert categories.status_code == 200
        assert sum(row["spend"] for row in categories.json()) == -30

        evidence = []
        offset = 0
        while True:
            page = client.get(
                "/transactions",
                params={
                    "start_date": "2024-02-01",
                    "end_date": "2024-02-29",
                    "q": "is:spend",
                    "limit": 2,
                    "offset": offset,
                },
                headers=AUTH_HEADERS,
            )
            assert page.status_code == 200
            payload = page.json()
            evidence.extend(payload["items"])
            offset += 2
            if len(evidence) >= payload["total"]:
                break
        assert len(evidence) == 3
        assert sum(row["amount"] for row in evidence) == -30


def test_adversarial_changes_remain_counted_until_confirmed_and_recompute():
    with SessionLocal() as db:
        seeded = seed_cashflow_ledger(db)
        # Same amount/date/description is a distinct provider event, not an
        # import replay: the independently expected January spend rises by 10.
        _add_transaction(db, seeded, "third-coffee", "card", 10, date(2024, 1, 20))
        # A pending row is inspectable but cannot enter realized totals.
        _add_transaction(db, seeded, "pending-extra", "card", 999, date(2024, 2, 10), pending=True)
        # Unresolved transfer candidates are intentionally still counted.
        out = _add_transaction(db, seeded, "candidate-out", "checking", 75, date(2024, 2, 10))
        inn = _add_transaction(db, seeded, "candidate-in", "payment", -75, date(2024, 2, 10))
        pair = TransferPair(txn_out_id=out.id, txn_in_id=inn.id, confirmed=False, detected_by="auto")
        db.add(pair)
        db.commit()
        pair_id = pair.id

    with TestClient(app) as client:
        before = client.get(
            "/analytics/cashflow-trend",
            params={"start_date": "2024-02-01", "end_date": "2024-02-29"},
            headers=AUTH_HEADERS,
        ).json()[0]
        assert (before["income"], before["expenses"], before["net"]) == (3075, 45, 3030)
        response = client.post(f"/transfers/{pair_id}/confirm", headers=AUTH_HEADERS)
        assert response.status_code == 200
        after = client.get(
            "/analytics/cashflow-trend",
            params={"start_date": "2024-02-01", "end_date": "2024-02-29"},
            headers=AUTH_HEADERS,
        ).json()[0]
        assert (after["income"], after["expenses"], after["net"]) == (3000, -30, 3030)

    # The extra genuine January charge remains visible after the February
    # transfer review; pending activity never enters either period.
    with TestClient(app) as client:
        january = client.get(
            "/analytics/spending-summary",
            params={"reporting_date": "2024-01-31"},
            headers=AUTH_HEADERS,
        ).json()
        assert january["total"] == 235
