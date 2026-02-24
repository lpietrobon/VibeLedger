from fastapi.testclient import TestClient
from app.main import app


def test_sync_missing_item_returns_404():
    with TestClient(app) as client:
        r = client.post('/sync/item/999999')
    assert r.status_code == 404


def test_annotation_missing_transaction_404():
    with TestClient(app) as client:
        r = client.patch('/transactions/999999/annotation', json={'notes': 'x'})
    assert r.status_code == 404
