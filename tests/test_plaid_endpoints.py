from fastapi.testclient import TestClient
from app.main import app


def test_create_link_token_contract():
    with TestClient(app) as client:
        r = client.post('/plaid/link-token/create', json={'user_id': 'u1'})
    assert r.status_code == 200
    assert 'link_token' in r.json()


def test_exchange_public_token_contract():
    with TestClient(app) as client:
        r = client.post('/plaid/public-token/exchange', json={'public_token': 'public-123'})
    assert r.status_code == 200
    assert r.json()['status'] == 'linked'
    assert r.json()['item_id'] == 'item-mock-123'
