"""Exercise the Plaid adapter with a fake SDK transport, never a bank."""
from datetime import date
from unittest.mock import Mock

import pytest

from app.services.plaid_client import PlaidClient


def adapter():
    client = PlaidClient()
    client._mock = False
    client._client = Mock()
    return client


def txn(identifier, **overrides):
    return {
        "transaction_id": identifier,
        "account_id": "checking",
        "date": date(2026, 8, 31),
        "amount": 19.50,
        "name": "Purchase",
        "pending": False,
        **overrides,
    }


def test_sync_reads_all_pages_and_preserves_added_modified_removed():
    client = adapter()
    client._client.transactions_sync.side_effect = [
        {"added": [txn("posted", pending_transaction_id="pending")], "modified": [], "removed": [{"transaction_id": "pending"}], "next_cursor": "page-two", "has_more": True},
        {"added": [txn("second")], "modified": [txn("old", amount=20)], "removed": [{"transaction_id": "deleted"}], "next_cursor": "done", "has_more": False},
    ]
    result = client.sync_transactions("test-access", "start")
    assert [t["transaction_id"] for t in result["added"]] == ["posted", "second"]
    assert result["added"][0]["_source"]["pending_transaction_id"] == "pending"
    assert result["modified"][0]["amount"] == 20
    assert result["removed"] == [{"transaction_id": "pending"}, {"transaction_id": "deleted"}]
    assert result["next_cursor"] == "done"
    assert [call.args[0].cursor for call in client._client.transactions_sync.call_args_list] == ["start", "page-two"]


def test_sync_page_failure_never_returns_partial_success():
    client = adapter()
    client._client.transactions_sync.side_effect = [{"added": [txn("first")], "next_cursor": "next", "has_more": True}, RuntimeError("provider unavailable")]
    with pytest.raises(RuntimeError, match="provider unavailable"):
        client.sync_transactions("test-access")


def test_historical_pagination_keeps_distinct_same_amount_purchases():
    client = adapter()
    client._client.transactions_get.side_effect = [{"transactions": [txn(f"t-{i}") for i in range(500)]}, {"transactions": [txn("last")]}]
    rows = client.get_historical_transactions("test-access", date(2026, 1, 1), date(2026, 8, 31))
    assert len(rows) == len({row["transaction_id"] for row in rows}) == 501
    assert [call.args[0].options.offset for call in client._client.transactions_get.call_args_list] == [0, 500]
    assert all(request.start_date == date(2026, 1, 1) for request in [call.args[0] for call in client._client.transactions_get.call_args_list])


def test_normalization_uses_posting_date_and_preserves_provider_evidence():
    raw = txn("posted", authorized_date=date(2026, 8, 29), name=None, personal_finance_category={"primary": "FOOD_AND_DRINK", "detailed": "FOOD_AND_DRINK_RESTAURANTS"})
    normalized = PlaidClient._normalize_txn(raw)
    assert normalized["date"] == "2026-08-31"
    assert normalized["name"] == ""
    assert normalized["plaid_category_primary"] == "FOOD_AND_DRINK"
    assert normalized["_source"]["personal_finance_category"]["detailed"] == "FOOD_AND_DRINK_RESTAURANTS"
    assert normalized["_source"]["authorized_date"] == date(2026, 8, 29)


def test_accounts_keep_currency_liability_type_and_unavailable_balances():
    client = adapter()
    client._client.accounts_get.return_value = {"accounts": [{"account_id": "card", "name": "Card", "type": "credit", "subtype": "credit card", "balances": {"current": 450, "available": None, "iso_currency_code": "USD", "limit": 1000}}, {"account_id": "checking", "name": "Checking", "type": "depository", "balances": {"current": None, "available": None, "iso_currency_code": "EUR"}}]}
    card, checking = client.get_accounts("test-access")
    assert card["type"] == "credit"
    assert card["current_balance"] == 450
    assert card["available_balance"] is None
    assert card["limit"] == 1000
    assert checking["iso_currency_code"] == "EUR"
    assert checking["current_balance"] is None
