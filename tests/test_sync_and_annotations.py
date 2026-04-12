from fastapi.testclient import TestClient
from app.db.session import SessionLocal
from app.main import app
from app.models.models import Item
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def test_sync_missing_item_returns_404():
    with TestClient(app) as client:
        r = client.post('/sync/item/999999', headers=AUTH_HEADERS)
    assert r.status_code == 404


def test_annotation_missing_transaction_404():
    with TestClient(app) as client:
        r = client.patch('/transactions/999999/annotation', json={'notes': 'x'}, headers=AUTH_HEADERS)
    assert r.status_code == 404


def test_sync_all_no_items():
    with TestClient(app) as client:
        r = client.post('/sync/all', headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json()["summary"] == "no active items"


def test_sync_all_syncs_active_items():
    with SessionLocal() as db:
        db.add(Item(plaid_item_id="all-1", access_token_encrypted=encrypt_token("tok"), status="active"))
        db.add(Item(plaid_item_id="all-2", access_token_encrypted=encrypt_token("tok"), status="active"))
        db.commit()

    with TestClient(app) as client:
        r = client.post('/sync/all', headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == "2/2 items synced"
    assert len(body["results"]) == 2
    assert all(res["status"] == "success" for res in body["results"])
