"""Supplemental integration/lifecycle checks; frozen INV-03 tests stay unchanged."""
from copy import deepcopy
from unittest.mock import Mock
from datetime import date

from app.db.session import SessionLocal
from app.services.sync_service import SyncService
from app.services.plaid_client import PlaidClient
from app.services.investment_sync import InvestmentSyncService, investment_summary
from app.models.models import InvestmentHolding, InvestmentValuation, Transaction
from tests.test_investment_ingestion import Provider, seed, START, END
from tests.test_sync_atomicity import BatchClient


def test_bank_sync_continues_after_investment_failure():
    with SessionLocal() as db:
        item_id=seed(db);p=Provider();p.fail=True
        try:InvestmentSyncService(p).sync_item(db,item_id,START,END)
        except RuntimeError:pass
        bank=BatchClient();bank.rows=[bank.record('first'),bank.record('second')]
        assert SyncService(bank).sync_item(db,item_id)['added']==2
        assert db.query(Transaction).count()==3
        assert db.query(InvestmentHolding).count()==0


def test_replaced_holdings_and_same_day_value_revisions_keep_source_provenance():
    with SessionLocal() as db:
        item_id=seed(db);p=Provider();svc=InvestmentSyncService(p)
        svc.sync_item(db,item_id,START,END)
        original=db.query(InvestmentValuation).one().original_raw_json
        p.holdings['holdings']=[]
        p.holdings['accounts'][0]['balances']['current']=1400
        svc.sync_item(db,item_id,START,END)
        assert not db.query(InvestmentHolding).one().is_current
        v=db.query(InvestmentValuation).one()
        assert v.revision==2 and v.original_raw_json==original and v.raw_json!=original
        assert investment_summary(db)['total_value']==1400


def test_holdings_adapter_uses_only_holdings_endpoint():
    p=PlaidClient();p._mock=False;p._client=Mock()
    expected=Provider().holdings
    p._client.investments_holdings_get.return_value=deepcopy(expected)
    assert p.get_investment_holdings('fake')==expected
    p._client.investments_holdings_get.assert_called_once()
    p._client.transactions_sync.assert_not_called()
