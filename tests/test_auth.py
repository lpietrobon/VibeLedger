from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import AUTH_HEADERS


def test_no_token_returns_401():
    with TestClient(app) as client:
        r = client.get("/transactions")
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid or missing bearer token"


def test_wrong_token_returns_401():
    with TestClient(app) as client:
        r = client.get("/transactions", headers={"Authorization": "Bearer wrong-token"})
    assert r.status_code == 401


def test_correct_token_passes():
    with TestClient(app) as client:
        r = client.get("/transactions", headers=AUTH_HEADERS)
    assert r.status_code == 200


def test_health_exempt_from_auth():
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_connect_start_exempt_from_auth():
    with TestClient(app) as client:
        # Will return 400 (invalid session) but NOT 401
        r = client.get("/connect/start", params={"session": "fake"})
    assert r.status_code == 400


def test_connect_complete_exempt_from_auth():
    with TestClient(app) as client:
        r = client.post("/connect/complete", json={"session_token": "bad", "public_token": "pub"})
    assert r.status_code == 400  # invalid session, not 401
