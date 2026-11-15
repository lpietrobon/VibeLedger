"""Atomic, opt-in investment ingestion. Never writes the spending ledger."""
import json
from datetime import date, timedelta, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.dialects.sqlite import insert

from app.core.time import utcnow
from app.models.models import (Account, Item, InvestmentSecurity, InvestmentHolding,
                               InvestmentActivity, InvestmentValuation, InvestmentSyncState)
from app.services.plaid_client import PlaidClient
from app.services.security import decrypt_token

INVESTMENT_TYPES = {'investment', 'brokerage'}


def validate_window(start, end):
    if not isinstance(start, date) or not isinstance(end, date) or start > end or (end-start).days >= 730:
        raise ValueError('investment window must be ordered and at most 730 inclusive days')


def encoded(value):
    return json.dumps(value, default=str, sort_keys=True, allow_nan=False)


def number(value, *, required=False):
    if value is None:
        if required:
            raise ValueError('required numeric value missing')
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('invalid numeric investment value') from None
    if not result.is_finite() or abs(result) >= Decimal('1e16'):
        raise ValueError('nonfinite or overflowing investment value')
    return result


def identifier(value):
    if not isinstance(value, str) or not value or len(value) > 128:
        raise ValueError('invalid investment identifier')
    return value


def currency(row):
    if row.get('unofficial_currency_code'):
        return 'UNOFFICIAL'
    value = row.get('iso_currency_code')
    return value.strip().upper() if isinstance(value, str) and value.strip() else None


class InvestmentSyncService:
    def __init__(self, client=None):
        self.client = client or PlaidClient()

    def sync_item(self, db, item_id, start, end):
        validate_window(start, end)
        item = db.get(Item, item_id)
        if item is None or item.status != 'active':
            raise ValueError('active investment item not found')
        # Atomic acquisition, including the first run, across service instances.
        db.execute(insert(InvestmentSyncState).values(item_id=item_id, status='never', account_ids_json='[]')
                   .on_conflict_do_nothing(index_elements=['item_id']))
        acquired = db.query(InvestmentSyncState).filter(
            InvestmentSyncState.item_id == item_id, InvestmentSyncState.status != 'running'
        ).update({'status':'running', 'last_attempt_at':utcnow()}, synchronize_session=False)
        if not acquired:
            db.rollback()
            raise ValueError('investment sync already running')
        db.commit()
        try:
            token = decrypt_token(item.access_token_encrypted)
            holdings = self.client.get_investment_holdings(token)
            activity = self.client.get_investment_transactions(token, start, end)
            now = utcnow()
            self._apply(db, item_id, holdings, activity, start, end, now)
            state = db.get(InvestmentSyncState, item_id)
            state.status = 'success'; state.last_success_at = now; state.error_type = None
            state.window_start = start; state.window_end = end
            db.commit()
        except Exception as exc:
            db.rollback()
            state = db.get(InvestmentSyncState, item_id)
            state.status = 'error'; state.error_type = type(exc).__name__[:128]
            db.commit()
            raise
        return {'status':'success', 'item_id':item_id, 'start_date':str(start), 'end_date':str(end)}

    def _apply(self, db, item_id, holdings, activity, start, end, now):
        # Missing collection keys are not empty successful snapshots.
        for payload, keys in [(holdings, ('accounts','holdings','securities')),
                              (activity, ('investment_transactions','securities'))]:
            if any(not isinstance(payload.get(k), list) for k in keys):
                raise ValueError('incomplete investment response')
        accounts = {}
        seen = set()
        for raw in holdings['accounts']:
            key = identifier(raw.get('account_id'))
            if key in seen:
                raise ValueError('duplicate investment account')
            seen.add(key)
            kind = str(raw.get('type') or '').strip().lower()
            if kind in {'depository','credit','loan','payment'}:
                continue  # Mixed Item: never refresh bank balances here.
            if kind not in INVESTMENT_TYPES:
                raise ValueError('unknown investment account classification')
            account = db.query(Account).filter_by(plaid_account_id=key).first()
            if account and (account.item_id != item_id or (account.type or '').lower() not in INVESTMENT_TYPES):
                raise ValueError('investment account identity conflict')
            if not account:
                account = Account(plaid_account_id=key, item_id=item_id, name=raw.get('name') or 'Investment', type=kind)
                db.add(account); db.flush()
            balances = raw.get('balances')
            if not isinstance(balances, dict):
                raise ValueError('missing investment balance metadata')
            account.type = kind
            account.name = raw.get('name') or account.name
            account.official_name = raw.get('official_name')
            account.mask = raw.get('mask')
            account.subtype = str(raw['subtype']) if raw.get('subtype') is not None else None
            account.current_balance = number(balances.get('current'))
            account.currency = currency(balances)
            accounts[key] = account
            valuation = db.query(InvestmentValuation).filter_by(account_id=account.id, as_of_date=now.date()).first()
            if not valuation:
                valuation = InvestmentValuation(account_id=account.id, as_of_date=now.date(),
                                                original_raw_json=encoded(raw), revision=1)
                db.add(valuation)
            elif valuation.raw_json != encoded(raw):
                valuation.revision += 1
            valuation.raw_json = encoded(raw)
            valuation.value = account.current_balance; valuation.currency = account.currency; valuation.observed_at = now
        for raw in holdings['securities'] + activity['securities']:
            key = identifier(raw.get('security_id'))
            security = db.get(InvestmentSecurity, key)
            if not security:
                security = InvestmentSecurity(security_id=key); db.add(security)
            security.raw_json = encoded(raw)
            db.flush()
        def security_key(raw, required=False):
            key = raw.get('security_id')
            if key is None and not required:
                return None
            if not db.get(InvestmentSecurity, identifier(key)):
                raise ValueError('unknown investment security')
            return key
        ids = [a.id for a in accounts.values()]
        if ids:
            db.query(InvestmentHolding).filter(InvestmentHolding.account_id.in_(ids)).update({'is_current':False})
        positions = set()
        for raw in holdings['holdings']:
            account = accounts.get(raw.get('account_id'))
            if account is None:
                raise ValueError('holding outside investment accounts')
            key = security_key(raw, True)
            if (account.id,key) in positions:
                raise ValueError('duplicate investment holding')
            positions.add((account.id,key))
            row = db.query(InvestmentHolding).filter_by(account_id=account.id, security_id=key).first()
            if not row:
                row = InvestmentHolding(account_id=account.id, security_id=key); db.add(row)
            row.quantity = number(raw.get('quantity')); row.value = number(raw.get('institution_value'))
            number(raw.get('institution_price'))
            row.currency = currency(raw); row.raw_json = encoded(raw); row.is_current = True; row.observed_at = now
            db.flush()
        received = set()
        for raw in activity['investment_transactions']:
            key = identifier(raw.get('investment_transaction_id'))
            if key in received:
                raise ValueError('duplicate investment activity')
            received.add(key)
            account = accounts.get(raw.get('account_id'))
            if account is None:
                raise ValueError('activity outside investment accounts')
            when = raw.get('date')
            if isinstance(when, str): when = date.fromisoformat(when)
            if not isinstance(when, date) or not start <= when <= end:
                raise ValueError('investment activity outside requested window')
            sec = security_key(raw)
            amount = number(raw.get('amount'), required=True)
            for field in ('quantity','price','fees'): number(raw.get(field))
            if not isinstance(raw.get('type'), str) or not raw['type']:
                raise ValueError('missing investment activity type')
            data = encoded(raw)
            row = db.query(InvestmentActivity).filter_by(provider_id=key).first()
            if row and (row.item_id != item_id or row.account_id != account.id):
                raise ValueError('investment activity identity conflict')
            if not row:
                row = InvestmentActivity(provider_id=key, item_id=item_id, account_id=account.id,
                                         original_raw_json=data, revision=1)
                db.add(row)
            elif row.raw_json != data or row.is_removed:
                row.revision += 1
            row.security_id=sec; row.date=when; row.amount=amount; row.type=raw['type']; row.raw_json=data; row.is_removed=False
            db.flush()
        # Reconcile only accounts present in this complete response and requested dates.
        if ids:
            old = db.query(InvestmentActivity).filter(InvestmentActivity.item_id==item_id,
                InvestmentActivity.account_id.in_(ids), InvestmentActivity.date>=start, InvestmentActivity.date<=end,
                InvestmentActivity.is_removed.is_(False)).all()
            for row in old:
                if row.provider_id not in received: row.is_removed=True; row.revision+=1
        db.get(InvestmentSyncState,item_id).account_ids_json=encoded(ids)


def investment_summary(db):
    now=utcnow().replace(tzinfo=timezone.utc); accounts=[]; total=Decimal(0); complete=True
    for a in db.query(Account).filter(Account.type.in_(INVESTMENT_TYPES)).order_by(Account.id):
        state=db.get(InvestmentSyncState,a.item_id)
        valuation = db.query(InvestmentValuation).filter_by(account_id=a.id).order_by(
            InvestmentValuation.as_of_date.desc(), InvestmentValuation.observed_at.desc()).first()
        observed = valuation.observed_at if valuation else None
        successful = state.last_success_at if state else None
        if successful and successful.tzinfo is None:
            successful = successful.replace(tzinfo=timezone.utc)
        if observed and observed.tzinfo is None: observed=observed.replace(tzinfo=timezone.utc)
        coverage='present' if state and a.id in json.loads(state.account_ids_json) else 'missing_from_latest_response'
        status='missing' if a.current_balance is None else 'unsupported' if a.currency!='USD' else 'available'
        fresh=bool(observed and successful and state.status=='success'
                   and now-min(observed,successful)<=timedelta(hours=24) and coverage=='present')
        if status!='available' or coverage!='present': complete=False
        else: total+=a.current_balance
        accounts.append({'account_id':a.id,'name':a.nickname or a.name,'subtype':a.subtype,
                         'value':float(a.current_balance) if a.current_balance is not None else None,
                         'currency':a.currency,'valuation_status':status,'coverage':coverage,
                         'freshness':'fresh' if fresh else 'stale' if observed else 'missing',
                         'observed_at':observed.isoformat() if observed else None})
    return {'accounts':accounts,'total_value':float(total) if accounts and complete else None,
            'history_coverage':'observed_only','duplicate_account_coverage':'unverified'}


def remove_investment_data(db,item_id,account_ids):
    for model in (InvestmentHolding,InvestmentValuation):
        db.query(model).filter(model.account_id.in_(account_ids)).delete(synchronize_session=False)
    db.query(InvestmentActivity).filter_by(item_id=item_id).delete(synchronize_session=False)
    db.query(InvestmentSyncState).filter_by(item_id=item_id).delete(synchronize_session=False)
