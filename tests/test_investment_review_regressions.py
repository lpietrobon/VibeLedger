"""Regressions from the independent INV-05 review."""
from unittest.mock import Mock
import pytest
from app.db.session import SessionLocal
from app.models.models import Account, InvestmentActivity, InvestmentHolding
from app.api.routes import accounts_summary
from app.services.plaid_client import PlaidClient
from tests.test_investment_ingestion import Provider, seed, service, START, END


def test_accounts_value_matches_observation():
    with SessionLocal() as db:
        item = seed(db)
        assert service(Provider()).sync_item(db, item, START, END)['status'] == 'success'
        db.query(Account).filter_by(plaid_account_id='broker').one().current_balance = 9999
        db.commit()
        result = accounts_summary(db)
        assert result['net_worth'] == 1350
        assert result['groups']['investment'][0]['current_balance'] == 1250


@pytest.mark.parametrize('collection', ['holdings', 'activity'])
def test_conflicting_security_rolls_back(collection):
    with SessionLocal() as db:
        item = seed(db); provider = Provider(); svc = service(provider)
        assert svc.sync_item(db, item, START, END)['status'] == 'success'
        getattr(provider, collection)['securities'].append(dict(security_id='fund', name='Different', type='equity'))
        provider.holdings['holdings'] = []
        provider.activity['investment_transactions'] = []
        with pytest.raises(ValueError, match='conflicting investment security'):
            svc.sync_item(db, item, START, END)
        assert db.query(InvestmentHolding).one().is_current
        assert not db.query(InvestmentActivity).one().is_removed


def test_missing_page_securities_preserves_activity():
    with SessionLocal() as db:
        item = seed(db); provider = Provider()
        assert service(provider).sync_item(db, item, START, END)['status'] == 'success'
        adapter = PlaidClient.__new__(PlaidClient)
        adapter._mock = False
        adapter._client = Mock()
        adapter._client.investments_transactions_get.return_value = {'investment_transactions': [], 'total_investment_transactions': 0}
        provider.get_investment_transactions = adapter.get_investment_transactions
        with pytest.raises(ValueError, match='incomplete investment securities'):
            service(provider).sync_item(db, item, START, END)
        assert not db.query(InvestmentActivity).one().is_removed
