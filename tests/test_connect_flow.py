from fastapi.testclient import TestClient
from app.main import app


def test_create_connect_session_and_status():
    with TestClient(app) as client:
        r = client.post('/connect/sessions', json={'user_id': 'luke'})
        assert r.status_code == 200
        body = r.json()
        assert 'connect_url' in body
        assert 'session_token' in body

        s = client.get(f"/connect/sessions/{body['session_token']}")
        assert s.status_code == 200
        assert s.json()['status'] == 'created'


def test_connect_complete_requires_valid_session():
    with TestClient(app) as client:
        r = client.post('/connect/complete', json={'session_token': 'bad', 'public_token': 'pub'})
        assert r.status_code == 400
