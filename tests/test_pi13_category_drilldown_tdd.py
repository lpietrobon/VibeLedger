"""PI-13 frozen category drilldown contract.

The oracle is intentionally independent of aggregate implementation.  The
fixture includes rows that must be inspected but must not enter the spend
population: pending activity and a confirmed transfer.  An unconfirmed
candidate remains counted, and a confirmed refund reduces the same category.
"""

from fastapi.testclient import TestClient

from app.main import app
from tests.category_drilldown_fixture import category_drilldown_ledger
from tests.conftest import AUTH_HEADERS
from app.db.session import SessionLocal


BOUNDS = {"start_date": "2032-04-01", "end_date": "2032-04-30"}


def _paged_ids(client, query, category=None):
    pages = []
    offset = 0
    while True:
        params = {**BOUNDS, "q": query, "limit": 2, "offset": offset}
        if category is not None:
            params["category"] = category
        body = client.get("/transactions", params=params, headers=AUTH_HEADERS).json()
        pages.append(body["items"])
        offset += 2
        if offset >= body["total"]:
            return pages


def test_exact_category_drilldown_matches_independent_spend_oracle_across_pages(category_drilldown_ledger):
    seeded = category_drilldown_ledger
    with TestClient(app) as client:
        pages = _paged_ids(client, "is:spend", category="FOOD/OTHER")

    ids = [row["id"] for page in pages for row in page]
    expected = seeded["oracle"]
    assert [[row["id"] for row in page] for page in pages] == [
        [seeded["transaction_ids"][key] for key in page]
        for page in expected["oracle"]["stable_descending_exact_pages"]
    ]
    assert {row_id for row_id in ids} == {
        seeded["transaction_ids"][key] for key in expected["oracle"]["exact_spend_ids"]
    }
    assert sum(row["amount"] for page in pages for row in page) == expected["oracle"]["exact_spend_amount"]


def test_parent_category_search_is_explicitly_broader_than_exact_drilldown(category_drilldown_ledger):
    seeded = category_drilldown_ledger
    with TestClient(app) as client:
        exact = _paged_ids(client, "is:spend", category="FOOD/OTHER")
        parent = _paged_ids(client, "is:spend category:FOOD")

    exact_ids = {row["id"] for page in exact for row in page}
    parent_ids = {row["id"] for page in parent for row in page}
    expected = seeded["oracle"]
    assert exact_ids == {seeded["transaction_ids"][key] for key in expected["oracle"]["exact_spend_ids"]}
    assert parent_ids == {seeded["transaction_ids"][key] for key in expected["oracle"]["parent_spend_ids"]}
    assert sum(row["amount"] for page in parent for row in page) == expected["oracle"]["parent_spend_amount"]


def test_category_spend_aggregate_is_hand_calculated_and_excludes_non_spend_states(category_drilldown_ledger):
    with TestClient(app) as client:
        response = client.get("/analytics/category-spend", params=BOUNDS, headers=AUTH_HEADERS)
    assert response.status_code == 200
    food = next(row for row in response.json() if row["category"] == "FOOD/OTHER")
    assert food["spend"] == 67
