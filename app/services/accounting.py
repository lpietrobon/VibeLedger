"""Shared SQL expressions for realized cashflow reporting.

Plaid amounts use the ledger sign convention: purchases are positive and money
entering an account is negative. An unconfirmed transfer is only a review
candidate, so it remains in realized totals until confirmed.
"""
from sqlalchemy import case, func, select

from app.models.models import Transaction, TransactionAnnotation, TransferPair


def exclude_confirmed_transfers(query):
    return query.filter(
        ~Transaction.id.in_(select(TransferPair.txn_out_id).where(TransferPair.confirmed.is_(True))),
        ~Transaction.id.in_(select(TransferPair.txn_in_id).where(TransferPair.confirmed.is_(True))),
    )


def posted_activity(query, *, include_transfers: bool = False):
    query = query.filter(Transaction.pending.is_(False))
    return query if include_transfers else exclude_confirmed_transfers(query)


def is_refund():
    return (Transaction.amount < 0) & TransactionAnnotation.refund_status.in_(["confirmed", "likely"])


def expense_amount():
    """Positive charges less confirmed/likely refunds, in the refund's posting period."""
    return case((is_refund(), Transaction.amount), (Transaction.amount > 0, Transaction.amount), else_=0)


def income_amount():
    return case(
        ((Transaction.amount < 0) & ~func.coalesce(is_refund(), False), -Transaction.amount),
        else_=0,
    )
