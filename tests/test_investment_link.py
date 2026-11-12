"""Internal Link preparation: fake transport only, no product activation."""
from unittest.mock import Mock

import pytest

from app.core.config import settings
from app.services.plaid_client import PlaidClient


def adapter():
    client = PlaidClient()
    client._mock = False
    client._client = Mock()
    client._client.link_token_create.return_value = {"link_token": "synthetic-link"}
    return client


def test_investment_link_does_not_require_bank_transactions(monkeypatch):
    monkeypatch.setattr(settings, "plaid_products", "transactions")
    client = adapter()
    assert client.create_investment_link_token("synthetic-user") == {"link_token": "synthetic-link"}
    request = client._client.link_token_create.call_args.args[0].to_dict()
    assert request["products"] == ["investments"]
    assert "transactions" not in request
    assert "access_token" not in request
    assert [call[0] for call in client._client.mock_calls] == ["link_token_create"]


def test_bank_link_remains_transactions(monkeypatch):
    monkeypatch.setattr(settings, "plaid_products", "transactions")
    client = adapter()
    client.create_link_token("synthetic-user")
    request = client._client.link_token_create.call_args.args[0].to_dict()
    assert request["products"] == ["transactions"]
    assert request["transactions"]["days_requested"] == 730


def test_investment_link_preserves_oauth_redirect(monkeypatch):
    monkeypatch.setattr(settings, "plaid_redirect_uri", "https://example.com/connect/oauth")
    client = adapter()
    client.create_investment_link_token("synthetic-user")
    assert client._client.link_token_create.call_args.args[0].redirect_uri == settings.plaid_redirect_uri


def test_investment_link_provider_failure_propagates():
    client = adapter()
    client._client.link_token_create.side_effect = RuntimeError("synthetic failure")
    with pytest.raises(RuntimeError, match="synthetic failure"):
        client.create_investment_link_token("synthetic-user")


def test_investment_link_mock_is_distinct():
    client = PlaidClient()
    assert client.create_investment_link_token("test")["link_token"].startswith("mock-investment-link-")
