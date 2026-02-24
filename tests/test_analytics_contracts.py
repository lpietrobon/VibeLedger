from fastapi.testclient import TestClient
from app.main import app


def test_analytics_endpoints_contract():
    with TestClient(app) as client:
        for path in [
            '/analytics/monthly-spend',
            '/analytics/category-spend',
            '/analytics/cashflow-trend',
        ]:
            r = client.get(path)
            assert r.status_code == 200
            assert isinstance(r.json(), list)
