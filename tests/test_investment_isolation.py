from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal, engine
from app.main import app
from app.models.models import Account, Item, Transaction, SyncState
from app.services.security import encrypt_token
from app.services.sync_service import SyncService


class MixedClient:
    def get_accounts(self, token):
        return [dict(account_id=k, name=k, type=t, iso_currency_code='USD', current_balance=100)
                for k, t in [('bank', 'depository'), ('broker', 'investment')]]

    def sync_transactions(self, token, cursor):
        return {'added': [dict(transaction_id=k, account_id=k, date='2026-11-01',
                               amount=v, name=k, pending=False)
                          for k, v in [('bank', 25), ('broker', 1000)]], 'next_cursor': 'done'}

    def get_historical_transactions(self, token, start, end):
        return self.sync_transactions(token, None)['added']


@pytest.mark.parametrize('historical', [False, True])
def test_mixed_sync_keeps_balances_but_not_investment_activity(historical):
    with SessionLocal() as db:
        item = Item(plaid_item_id='mixed', access_token_encrypted=encrypt_token('fake'))
        db.add(item)
        db.commit()
        svc = SyncService(MixedClient())
        result = (svc.sync_item_historical(db, item.id, date(2026, 11, 1), date(2026, 11, 2))
                  if historical else svc.sync_item(db, item.id))
        assert result['added'] == 1
        assert [t.name for t in db.query(Transaction)] == ['bank']
        assert db.query(Account).count() == 2
        if not historical:
            assert db.query(SyncState).one().cursor == 'done'


def test_legacy_investment_rows_are_retained_but_not_reported():
    with SessionLocal() as db:
        item = Item(plaid_item_id='mixed', access_token_encrypted=encrypt_token('fake'))
        db.add(item)
        db.flush()
        for key, kind, amount in [('bank', 'depository', 25), ('broker', 'investment', 1000)]:
            a = Account(plaid_account_id=key, item_id=item.id, name=key, type=kind, currency='USD')
            db.add(a)
            db.flush()
            db.add(Transaction(plaid_transaction_id=key, item_id=item.id, account_id=a.id,
                               date=date(2026, 11, 1), amount=amount, name=key, pending=False))
        db.commit()
    with TestClient(app) as client:
        headers = {'Authorization': 'Bearer test-token'}
        result = client.get('/transactions', headers=headers).json()
        assert result['total'] == 1
        for include in ['true', 'false']:
            result = client.get('/analytics/cashflow-trend', params={'include_transfers': include}, headers=headers)
            assert result.status_code == 200
            assert sum(r['expenses'] for r in result.json()) == 25
    with SessionLocal() as db:
        assert db.query(Transaction).count() == 2
        assert db.execute(text('SELECT count(*) FROM effective_transactions')).scalar() == 1


@pytest.mark.parametrize('kind', [None, '', 'other', 'investment', 'brokerage'])
def test_unknown_and_investment_accounts_fail_closed(kind):
    from app.services.account_domain import spending_activity
    with SessionLocal() as db:
        item = Item(plaid_item_id='unknown', access_token_encrypted=encrypt_token('fake'))
        db.add(item)
        db.flush()
        a = Account(plaid_account_id='unknown', item_id=item.id, name='Schwab checking', type=kind)
        db.add(a)
        db.flush()
        db.add(Transaction(plaid_transaction_id='unknown', item_id=item.id, account_id=a.id,
                           date=date(2026, 11, 1), amount=1000, name='unknown', pending=False))
        db.flush()
        assert spending_activity(db.query(Transaction)).count() == 0


def test_bank_responses_unchanged_after_legacy_investment_rows_and_pair():
    from app.models.models import TransferPair
    endpoints = ['/transactions', '/categories', '/transactions/search-suggestions?q=merchant:',
                 '/analytics/monthly-spend', '/analytics/category-spend', '/analytics/cashflow-trend',
                 '/analytics/recurring', '/analytics/overview', '/analytics/spending-summary',
                 '/analytics/cumulative-spend', '/transfers']
    with SessionLocal() as db:
        item = Item(plaid_item_id='baseline', access_token_encrypted=encrypt_token('fake'))
        db.add(item)
        db.flush()
        bank = Account(plaid_account_id='bank', item_id=item.id, name='Schwab checking',
                       type='depository', currency='USD', current_balance=100)
        broker = Account(plaid_account_id='broker', item_id=item.id, name='Schwab IRA',
                         type='investment', currency='USD', current_balance=200)
        db.add_all([bank, broker]); db.flush()
        t = Transaction(plaid_transaction_id='bank', item_id=item.id, account_id=bank.id,
                        date=date.today(), amount=25, name='Groceries', pending=False)
        db.add(t); db.commit()
        item_id, broker_id, bank_tx = item.id, broker.id, t.id
    with TestClient(app) as client:
        headers = {'Authorization': 'Bearer test-token'}
        def snapshot():
            result = {}
            for endpoint in endpoints:
                response = client.get(endpoint, headers=headers)
                assert response.status_code == 200, (endpoint, response.text)
                result[endpoint] = response.json()
            return result
        before = snapshot()
        with SessionLocal() as db:
            t = Transaction(plaid_transaction_id='investment', item_id=item_id, account_id=broker_id,
                            date=date.today(), amount=-25, name='Dividend', merchant_name='Investment only',
                            plaid_category_primary='INVESTMENT_ONLY', pending=False)
            db.add(t); db.flush()
            db.add(TransferPair(txn_out_id=bank_tx, txn_in_id=t.id, confirmed=False))
            db.commit()
        assert snapshot() == before


@pytest.mark.parametrize('historical', [False, True])
def test_unclassified_provider_account_rolls_back_without_advancing_cursor(historical):
    class UnknownClient(MixedClient):
        def get_accounts(self, token):
            return [dict(account_id='bank', name='Unclassified', type=None)]
    with SessionLocal() as db:
        item = Item(plaid_item_id='unknown-sync', access_token_encrypted=encrypt_token('fake'))
        db.add(item); db.flush()
        db.add(SyncState(item_id=item.id, cursor='prior')); db.commit()
        svc = SyncService(UnknownClient())
        with pytest.raises(ValueError, match='classification unavailable'):
            if historical:
                svc.sync_item_historical(db, item.id, date(2026, 11, 1), date(2026, 11, 2))
            else:
                svc.sync_item(db, item.id)
        assert db.query(Transaction).count() == 0
        assert db.query(Account).count() == 0
        assert db.query(SyncState).one().cursor == 'prior'
