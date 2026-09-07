from fastapi.testclient import TestClient

from app.main import app
from tests.cashflow_fixture import seed_cashflow_ledger
from app.db.session import SessionLocal
from tests.conftest import AUTH_HEADERS


def test_sankey_exposes_residual_net_refund_credits_without_disabling_flow():
    with SessionLocal() as db:
        seed_cashflow_ledger(db)
        db.commit()

    with TestClient(app) as client:
        response = client.get(
            "/analytics/cashflow-sankey",
            params={"start_date": "2024-02-01", "end_date": "2024-02-29"},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["sankey_supported"] is True
    assert payload["income"] == 3000
    assert payload["total_spend"] == -30
    assert payload["net_refund_credits"] == 120
    assert payload["net_refund_credit_categories"] == [{"category": "SHOPPING", "amount": 120}]
    assert sum(bucket["amount"] for bucket in payload["buckets"]) == 90
