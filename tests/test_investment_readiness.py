"""Coverage diagnostics must not activate products or claim untested coverage."""
import json
from unittest.mock import Mock

import pytest

from app.services.plaid_client import PlaidClient


def adapter(item):
    client = PlaidClient()
    client._mock = False
    client._client = Mock()
    client._client.item_get.return_value = {"item": item}
    client._client.accounts_get.return_value = {"accounts": [
        {"account_id": "private-account", "name": "Private account name", "mask": "1234",
         "type": "investment", "subtype": "roth", "balances": {"current": 987654.32, "iso_currency_code": "USD"}},
        {"account_id": "second", "type": "investment", "subtype": "roth", "balances": {"current": None}},
        {"account_id": "cash-management", "type": "depository", "subtype": "checking", "balances": {"current": 100}},
    ]}
    return client


@pytest.mark.parametrize('field', ['available_products', 'billed_products', 'consented_products'])
def test_product_metadata_is_not_proof_of_coverage(field):
    client = adapter({field: ['investments'], 'item_id': 'private-item', 'webhook': 'private-url'})
    result = client.get_investment_readiness('synthetic-access')
    assert result['investment_products'][field] is True
    assert result['coverage_verified'] is False
    assert result['source'] == 'provider_metadata'
    assert result['account_types'] == [
        {'type': 'depository', 'subtype': 'checking', 'count': 1},
        {'type': 'investment', 'subtype': 'roth', 'count': 2},
    ]
    serialized = json.dumps(result)
    for private in ['private-account', 'Private account name', '1234', '987654', 'private-item', 'private-url', 'synthetic-access']:
        assert private not in serialized
    assert [call[0] for call in client._client.mock_calls] == ['item_get', 'accounts_get']
    assert client._client.item_get.call_args.args[0].access_token == 'synthetic-access'


def test_missing_metadata_is_unknown_not_unsupported():
    client = adapter({})
    result = client.get_investment_readiness('synthetic-access')
    assert result['investment_products'] == {
        'available_products': None, 'billed_products': None, 'consented_products': None,
    }
    client._client.item_get.return_value = {'item': {'available_products': []}}
    assert client.get_investment_readiness('synthetic-access')['investment_products']['available_products'] is False


def test_provider_failure_is_not_a_success_or_partial_report():
    client = adapter({})
    client._client.accounts_get.side_effect = RuntimeError('provider unavailable')
    with pytest.raises(RuntimeError, match='provider unavailable'):
        client.get_investment_readiness('synthetic-access')


def test_mock_is_explicitly_unverified_and_does_not_invent_investment_access():
    result = PlaidClient().get_investment_readiness('synthetic-access')
    assert result['source'] == 'mock'
    assert result['coverage_verified'] is False
    assert all(value is None for value in result['investment_products'].values())


def test_unknown_account_type_stays_unknown():
    client = adapter({})
    client._client.accounts_get.return_value = {'accounts': [{'account_id': 'unknown', 'balances': {}}]}
    assert client.get_investment_readiness('synthetic-access')['account_types'] == [
        {'type': 'unknown', 'subtype': 'unknown', 'count': 1},
    ]
