from unittest.mock import Mock
import pytest
from app.core.config import settings


@pytest.fixture(autouse=True)
def enable_link_for_test(monkeypatch):
    monkeypatch.setattr(settings, "investment_link_enabled", True)

from fastapi.testclient import TestClient
from app.main import app
from app.db.session import SessionLocal
from app.models.models import Item, ConnectSession
from app.services.security import encrypt_token
from app.services.plaid_client import PlaidClient
from tests.conftest import AUTH_HEADERS


def test_update_adapter_contract():
    c = PlaidClient()
    c._mock = False
    c._client = Mock()
    c._client.link_token_create.return_value = {'link_token': 'synthetic'}
    assert c.create_investment_update_token('user', 'secret')['link_token'] == 'synthetic'
    req = c._client.link_token_create.call_args.args[0].to_dict()
    assert req['access_token'] == 'secret'
    assert req['additional_consented_products'] == ['investments']
    assert req['update']['account_selection_enabled'] is True
    assert 'products' not in req
    assert 'transactions' not in req


def seed():
    with SessionLocal() as db:
        item = Item(plaid_item_id='existing-schwab', access_token_encrypted=encrypt_token('synthetic-access'))
        db.add(item); db.commit(); db.refresh(item)
        return item.id


def test_update_completion_preserves_item_and_requires_provider_consent(monkeypatch):
    with TestClient(app) as client:
        item_id = seed()
        path = f'/items/{item_id}/investments/connect'
        assert client.post(path).status_code == 401
        r = client.post(path, headers=AUTH_HEADERS)
        assert r.status_code == 200
        session_token = r.json()['session_token']
        monkeypatch.setattr(PlaidClient, 'exchange_public_token', lambda *args: (_ for _ in ()).throw(AssertionError('must not exchange')))
        monkeypatch.setattr(PlaidClient, 'get_investment_readiness', lambda *args: {'investment_products': {'consented_products': False}})
        body = {'session_token': session_token}
        assert client.post('/connect/complete', json=body).status_code == 409
        monkeypatch.setattr(PlaidClient, 'get_investment_readiness', lambda *args: {'investment_products': {'consented_products': True}})
        response = client.post('/connect/complete', json=body)
        assert response.status_code == 200
        assert response.json()['status'] == 'consented'
        assert client.post('/connect/complete', json=body).status_code == 400
        with SessionLocal() as db:
            assert db.query(Item).count() == 1
            assert db.get(Item, item_id).plaid_item_id == 'existing-schwab'
            assert db.query(ConnectSession).one().status == 'completed'


def test_missing_item_and_bank_token_requirement():
    with TestClient(app) as client:
        assert client.post('/items/999/investments/connect', headers=AUTH_HEADERS).status_code == 404
        s = client.post('/connect/sessions', json={}, headers=AUTH_HEADERS).json()
        assert client.post('/connect/complete', json={'session_token': s['session_token']}).status_code == 400


def test_expired_or_removed_connection_cannot_complete(monkeypatch):
    from datetime import timedelta
    from app.core.time import utcnow
    with TestClient(app) as client:
        item_id = seed()
        s = client.post(f'/items/{item_id}/investments/connect', headers=AUTH_HEADERS).json()
        with SessionLocal() as db:
            session = db.query(ConnectSession).one()
            session.expires_at = utcnow() - timedelta(seconds=1)
            db.commit()
        body = {'session_token': s['session_token']}
        assert client.post('/connect/complete', json=body).status_code == 400
        with SessionLocal() as db:
            db.query(ConnectSession).one().expires_at = utcnow() + timedelta(minutes=10)
            db.delete(db.get(Item, item_id)); db.commit()
        assert client.post('/connect/complete', json=body).status_code == 409


def test_provider_error_is_redacted_and_retryable(monkeypatch):
    with TestClient(app) as client:
        item_id = seed()
        s = client.post(f'/items/{item_id}/investments/connect', headers=AUTH_HEADERS).json()
        def fail(*args):
            raise RuntimeError('sensitive-provider-body')
        monkeypatch.setattr(PlaidClient, 'get_investment_readiness', fail)
        r = client.post('/connect/complete', json={'session_token': s['session_token']})
        assert r.status_code == 502
        assert 'sensitive-provider-body' not in r.text
        with SessionLocal() as db:
            assert db.query(ConnectSession).one().status == 'created'


def test_connect_schema_patch_preserves_legacy_sessions():
    from sqlalchemy import create_engine, text
    from app.db.schema_patches import apply_patches
    engine = create_engine('sqlite://')
    # Use current schema minus the added column to exercise an old deployment.
    from app.db.base import Base
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text('ALTER TABLE connect_sessions DROP COLUMN purpose'))
        conn.execute(text("INSERT INTO connect_sessions (session_token,user_id,status,created_at,expires_at) VALUES ('legacy','user','created','2026-01-01','2027-01-01')"))
    apply_patches(engine)
    apply_patches(engine)
    with engine.connect() as conn:
        assert conn.execute(text('SELECT purpose FROM connect_sessions')).scalar() == 'bank'


def test_unreleased_link_cannot_contact_provider(monkeypatch):
    monkeypatch.setattr(settings, "investment_link_enabled", False)
    monkeypatch.setattr(PlaidClient, "create_investment_update_token", lambda *args: pytest.fail("must not contact provider"))
    with TestClient(app) as client:
        item_id = seed()
        assert client.post(f"/items/{item_id}/investments/connect", headers=AUTH_HEADERS).status_code == 409


def test_cleanup_failure_does_not_misreport_successful_consent(monkeypatch):
    import app.api.routes as routes
    with TestClient(app) as client:
        item_id = seed()
        s = client.post(f"/items/{item_id}/investments/connect", headers=AUTH_HEADERS).json()
        monkeypatch.setattr(PlaidClient, "get_investment_readiness", lambda *args: {"investment_products": {"consented_products": True}})
        def fail(*args):
            raise RuntimeError("private teardown details")
        monkeypatch.setattr(routes, "_run_connect_tunnel", fail)
        r = client.post('/connect/complete', json={'session_token': s['session_token']})
        assert r.status_code == 200
        assert r.json()['status'] == 'consented'
        assert r.json()['cleanup_pending'] is True
        assert 'private teardown' not in r.text
