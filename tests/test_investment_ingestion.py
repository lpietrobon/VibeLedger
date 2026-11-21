"""Frozen INV-03 contracts: synthetic provider data, no live credentials or calls."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db.session import SessionLocal, engine
from app.models.models import Account, Item, Transaction, SyncState
from app.services.security import encrypt_token
from app.services.plaid_client import PlaidClient
from app.main import app

START, END = date(2026, 1, 1), date(2026, 1, 31)


class Provider:
    def __init__(self):
        self.holdings = {
            'accounts': [dict(account_id='broker', name='IRA', type='investment', subtype='ira',
                              balances=dict(current=1250, iso_currency_code='USD')),
                         dict(account_id='bank', name='Checking', type='depository',
                              balances=dict(current=99999, iso_currency_code='USD'))],
            'securities': [dict(security_id='fund', name='Fund', type='mutual fund')],
            'holdings': [dict(account_id='broker', security_id='fund', quantity=10,
                             institution_value=1200, institution_price=120,
                             iso_currency_code='USD')],
        }
        self.activity = {'investment_transactions': [
            dict(investment_transaction_id='buy', account_id='broker', security_id='fund',
                 date=START, amount=1200, quantity=10, type='buy', subtype='buy', name='Fund buy',
                 iso_currency_code='USD')], 'securities': []}
        self.fail = False

    def get_investment_holdings(self, token):
        return deepcopy(self.holdings)

    def get_investment_transactions(self, token, start, end):
        if self.fail:
            raise RuntimeError('SECRET-provider-token-must-not-be-stored')
        return deepcopy(self.activity)


def seed(db):
    item = Item(plaid_item_id='investment-item', access_token_encrypted=encrypt_token('fake'))
    db.add(item); db.flush()
    bank = Account(plaid_account_id='bank', item_id=item.id, name='Checking', type='depository',
                   current_balance=100, currency='USD')
    db.add(bank); db.flush()
    db.add(Transaction(plaid_transaction_id='groceries', account_id=bank.id, item_id=item.id,
                       date=START, amount=25, name='Groceries', pending=False))
    db.add(SyncState(item_id=item.id, cursor='bank-unchanged'))
    db.commit()
    return item.id


def service(provider):
    from app.services.investment_sync import InvestmentSyncService
    return InvestmentSyncService(provider)


def test_replay_is_idempotent_and_never_writes_bank_activity_or_double_counts():
    from app.models.models import InvestmentHolding, InvestmentActivity, InvestmentValuation
    from app.services.investment_sync import investment_summary
    from app.api.routes import accounts_summary
    with SessionLocal() as db:
        item_id = seed(db); provider = Provider(); svc = service(provider)
        for _ in range(2):
            assert svc.sync_item(db, item_id, START, END)['status'] == 'success'
        assert db.query(InvestmentHolding).count() == 1
        assert db.query(InvestmentActivity).count() == 1
        assert db.query(InvestmentValuation).count() == 1
        assert db.query(Transaction).count() == 1
        assert db.query(SyncState).one().cursor == 'bank-unchanged'
        assert db.query(Account).filter_by(plaid_account_id='bank').one().current_balance == 100
        assert investment_summary(db)['total_value'] == 1250
        assert accounts_summary(db)['net_worth'] == 1350  # not 2550 including holdings twice
        assert db.query(InvestmentActivity).one().revision == 1


def test_partial_failure_retains_last_good_values_and_sanitizes_error_then_retry():
    from app.models.models import InvestmentSyncState, InvestmentActivity
    from app.services.investment_sync import investment_summary
    with SessionLocal() as db:
        item_id=seed(db); p=Provider(); svc=service(p)
        svc.sync_item(db,item_id,START,END)
        last=db.query(InvestmentSyncState).one().last_success_at
        p.holdings['accounts'][0]['balances']['current']=2000; p.fail=True
        with pytest.raises(RuntimeError): svc.sync_item(db,item_id,START,END)
        state=db.query(InvestmentSyncState).one()
        assert state.last_success_at == last
        assert state.error_type == 'RuntimeError'
        assert 'SECRET' not in str(state.__dict__)
        assert investment_summary(db)['total_value'] == 1250
        assert investment_summary(db)['accounts'][0]['freshness'] == 'stale'
        assert db.query(InvestmentActivity).count() == 1
        p.fail=False; svc.sync_item(db,item_id,START,END)
        assert investment_summary(db)['total_value'] == 2000


def test_corrections_soft_removal_and_reappearance_are_window_scoped():
    from app.models.models import InvestmentActivity
    with SessionLocal() as db:
        item_id=seed(db); p=Provider(); svc=service(p)
        svc.sync_item(db,item_id,START,END)
        p.activity['investment_transactions'][0]['amount']=1100
        svc.sync_item(db,item_id,START,END)
        row=db.query(InvestmentActivity).one(); assert row.amount == 1100 and row.revision == 2
        p.activity['investment_transactions']=[]
        svc.sync_item(db,item_id,date(2026,2,1),date(2026,2,28))
        assert not db.query(InvestmentActivity).one().is_removed
        svc.sync_item(db,item_id,START,END)
        assert db.query(InvestmentActivity).one().is_removed
        p.activity=Provider().activity
        svc.sync_item(db,item_id,START,END)
        assert not db.query(InvestmentActivity).one().is_removed


@pytest.mark.parametrize('fault',['foreign_account','unknown_type','invalid_security','outside_window','nan'])
def test_invalid_batches_roll_back_all_investment_writes(fault):
    from app.models.models import InvestmentActivity, InvestmentHolding
    with SessionLocal() as db:
        item_id=seed(db); p=Provider()
        if fault=='foreign_account':
            other=Item(plaid_item_id='other',access_token_encrypted=encrypt_token('other'))
            db.add(other);db.flush()
            db.add(Account(plaid_account_id='broker',item_id=other.id,name='Other',type='investment'))
            db.commit()
        if fault=='unknown_type': p.holdings['accounts'][0]['type']=None
        if fault=='invalid_security': p.activity['investment_transactions'][0]['security_id']='missing'
        if fault=='outside_window': p.activity['investment_transactions'][0]['date']=date(2025,1,1)
        if fault=='nan': p.holdings['holdings'][0]['institution_value']=float('nan')
        with pytest.raises(ValueError): service(p).sync_item(db,item_id,START,END)
        assert db.query(InvestmentActivity).count()==0
        assert db.query(InvestmentHolding).count()==0
        assert db.query(Transaction).count()==1


@pytest.mark.parametrize('value,currency,expected',[(None,'USD','missing'),(1250,'EUR','unsupported'),(1250,None,'unsupported')])
def test_missing_or_unsupported_values_are_not_zero_or_nominal_totals(value,currency,expected):
    from app.services.investment_sync import investment_summary
    with SessionLocal() as db:
        item_id=seed(db);p=Provider()
        p.holdings['accounts'][0]['balances']={'current':value,'iso_currency_code':currency}
        service(p).sync_item(db,item_id,START,END)
        result=investment_summary(db)
        assert result['total_value'] is None
        assert result['accounts'][0]['valuation_status']==expected


def test_investment_only_item_and_absent_account_preserves_last_good_with_missing_coverage():
    from app.services.investment_sync import investment_summary
    with SessionLocal() as db:
        i=Item(plaid_item_id='only',access_token_encrypted=encrypt_token('fake'));db.add(i);db.commit()
        p=Provider();p.holdings['accounts']=p.holdings['accounts'][:1]
        svc=service(p);svc.sync_item(db,i.id,START,END)
        assert db.query(Transaction).count()==0
        p.holdings={'accounts':[],'holdings':[],'securities':[]};p.activity={'investment_transactions':[],'securities':[]}
        svc.sync_item(db,i.id,START,END)
        result=investment_summary(db)
        assert result['accounts'][0]['coverage']=='missing_from_latest_response'
        assert result['total_value'] is None


def test_ingestion_preserves_spending_responses_and_removal_cleans_investment_rows():
    from app.models.models import InvestmentActivity, InvestmentHolding, InvestmentValuation, InvestmentSyncState
    with SessionLocal() as db: item_id=seed(db)
    with TestClient(app) as c:
        h={'Authorization':'Bearer test-token'}
        paths=['/transactions','/analytics/cashflow-trend?include_transfers=true','/analytics/monthly-spend',
               '/analytics/category-spend','/analytics/recurring','/categories']
        before={p:c.get(p,headers=h).json() for p in paths}
        with SessionLocal() as db: service(Provider()).sync_item(db,item_id,START,END)
        assert {p:c.get(p,headers=h).json() for p in paths}==before
        assert c.post(f'/items/{item_id}/remove',headers=h).status_code==200
    with SessionLocal() as db:
        for model in [InvestmentActivity,InvestmentHolding,InvestmentValuation,InvestmentSyncState]:
            assert db.query(model).count()==0


def test_adapter_reads_all_pages_and_never_uses_bank_sync():
    p=PlaidClient();p._mock=False;p._client=Mock()
    def row(key):return dict(investment_transaction_id=key)
    p._client.investments_transactions_get.side_effect=[
        {'investment_transactions':[row('a')],'total_investment_transactions':2,'securities':[]},
        {'investment_transactions':[row('b')],'total_investment_transactions':2,'securities':[]}]
    result=p.get_investment_transactions('fake',START,END)
    assert [r['investment_transaction_id'] for r in result['investment_transactions']]==['a','b']
    assert [c.args[0].options.offset for c in p._client.investments_transactions_get.call_args_list]==[0,1]
    p._client.transactions_sync.assert_not_called()


@pytest.mark.parametrize('second',[{'investment_transactions':[],'total_investment_transactions':2},
                                   {'investment_transactions':[{'investment_transaction_id':'a'}],'total_investment_transactions':2},
                                   {'investment_transactions':[{'investment_transaction_id':'b'}],'total_investment_transactions':3}])
def test_adapter_rejects_incomplete_unstable_or_duplicate_pages(second):
    p=PlaidClient();p._mock=False;p._client=Mock()
    p._client.investments_transactions_get.side_effect=[
        {'investment_transactions':[{'investment_transaction_id':'a'}],'total_investment_transactions':2},second]
    with pytest.raises(ValueError):p.get_investment_transactions('fake',START,END)


def test_live_sync_route_is_default_disabled():
    with TestClient(app) as c:
        r=c.post('/investments/sync/1?start_date=2026-01-01&end_date=2026-01-31',
                 headers={'Authorization':'Bearer test-token'})
        assert r.status_code==409


def test_concurrent_run_is_rejected_and_old_success_is_stale():
    from app.models.models import InvestmentSyncState
    from app.services.investment_sync import investment_summary
    from app.core.time import utcnow
    with SessionLocal() as db:
        item_id=seed(db);p=Provider();svc=service(p);svc.sync_item(db,item_id,START,END)
        state=db.query(InvestmentSyncState).one();state.status='running'
        state.last_success_at=utcnow()-timedelta(days=2);db.commit()
        assert investment_summary(db)['accounts'][0]['freshness']=='stale'
        with pytest.raises(ValueError,match='running'):svc.sync_item(db,item_id,START,END)


def test_schema_creation_is_additive_and_repeatable():
    from app.db.base import Base
    with SessionLocal() as db:seed(db)
    Base.metadata.create_all(engine);Base.metadata.create_all(engine)
    assert {'investment_holdings','investment_activity','investment_valuations','investment_sync_state','investment_securities'} <= set(inspect(engine).get_table_names())
    with SessionLocal() as db:assert db.query(Transaction).count()==1
