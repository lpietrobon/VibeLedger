"""Account-level spending boundary. Institution names never classify accounts."""
from sqlalchemy import select, func
from app.models.models import Account, Transaction

BANK_TYPES = ("depository", "credit", "loan", "payment")


def is_spending_account(account):
    return account is not None and (account.type or "").strip().lower() in BANK_TYPES


def spending_account_ids():
    return select(Account.id).where(func.lower(func.trim(Account.type)).in_(BANK_TYPES))


def spending_activity(query):
    return query.filter(Transaction.account_id.in_(spending_account_ids()))


def spending_transaction_ids():
    return select(Transaction.id).where(Transaction.account_id.in_(spending_account_ids()))


def spending_transfer_predicate(pair):
    ids = spending_transaction_ids()
    return ((pair.txn_out_id.in_(ids) & pair.txn_in_id.in_(ids))
            | (pair.confirmed.is_(True) & (pair.txn_out_id.in_(ids) | pair.txn_in_id.in_(ids))))
