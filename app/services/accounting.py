"""Shared SQL expressions for realized cashflow reporting.

Plaid amounts use the ledger sign convention: purchases are positive and money
entering an account is negative. An unconfirmed transfer is only a review
candidate, so it remains in realized totals until confirmed.
"""
import calendar
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import case, func, select

from app.models.models import Account, Transaction, TransactionAnnotation, TransferPair


def comparison_bounds(reporting_date: date, granularity: str = "monthly"):
    """Inclusive MTD/YTD and calendar-aligned prior bounds (CF-02)."""
    if granularity == "yearly":
        previous_year = reporting_date.year - 1
        previous_end = date(previous_year, reporting_date.month, min(
            reporting_date.day, calendar.monthrange(previous_year, reporting_date.month)[1]))
        return date(reporting_date.year, 1, 1), reporting_date, date(previous_year, 1, 1), previous_end
    start = reporting_date.replace(day=1)
    prior_last = start - timedelta(days=1)
    complete_month = reporting_date.day == calendar.monthrange(reporting_date.year, reporting_date.month)[1]
    prior_end = prior_last if complete_month else prior_last.replace(day=min(reporting_date.day, prior_last.day))
    return start, reporting_date, prior_last.replace(day=1), prior_end


def currency_expression(transaction=Transaction, account=Account):
    """Provider currency wins; account currency is explicit fallback evidence.

    An unofficial currency must not fall back to the account's ISO currency.
    Malformed provider JSON cannot supply trustworthy currency evidence.
    """
    raw = case((func.json_valid(transaction.raw_json), transaction.raw_json), else_="{}")
    provider = func.nullif(func.upper(func.trim(func.json_extract(raw, "$.iso_currency_code"))), "")
    unofficial = func.nullif(func.trim(func.json_extract(raw, "$.unofficial_currency_code")), "")
    account_currency = func.nullif(func.upper(func.trim(account.currency)), "")
    return case(
        (transaction.raw_json.is_not(None) & ~func.json_valid(transaction.raw_json), None),
        (unofficial.is_not(None), "UNOFFICIAL"),
        (provider.is_not(None) & account_currency.is_not(None) & (provider != account_currency), "CONFLICT"),
        else_=func.coalesce(provider, account_currency),
    )


def currency_reporting(currencies):
    """Refuse unsupported nominal sums without changing successful API shapes."""
    values = set(currencies)
    known = sorted(value for value in values if value is not None)
    status = "empty" if not values else "unknown" if None in values else "mixed" if len(values) > 1 else "single"
    metadata = {
        "currency": known[0] if status == "single" else None,
        "currency_status": status,
        "currencies": known,
        "history_coverage": "unverified",
        "duplicate_account_coverage": "unverified",
        "qualification": "Recorded activity only. Historical and duplicate-account coverage are unverified; missing records are not verified zero spending.",
    }
    if values and values != {"USD"}:
        raise HTTPException(status_code=422, detail={
            "code": "unsupported_currency_scope",
            "message": "This aggregate requires known USD currency throughout its scope. Mixed, unknown, and non-USD aggregates are unsupported; no conversion is performed.",
            **metadata,
        })
    return metadata


def reporting_scope(db, start=None, end=None, *, include_transfers=False, expense_only=False):
    """Qualify the same posted scope as the aggregate without exporting its rows."""
    q = db.query(currency_expression(), func.count(Transaction.id), func.min(Transaction.date), func.max(Transaction.date)).join(
        Account, Account.id == Transaction.account_id)
    q = posted_activity(q, include_transfers=include_transfers)
    if start is not None:
        q = q.filter(Transaction.date >= start)
    if end is not None:
        q = q.filter(Transaction.date <= end)
    if expense_only:
        q = q.filter(Transaction.amount > 0)
    rows = q.group_by(currency_expression()).all()
    metadata = currency_reporting(row[0] for row in rows)
    metadata.update({
        "start_date": str(start) if start else None,
        "end_date": str(end) if end else None,
        "recorded_row_count": sum(row[1] for row in rows),
        "first_recorded_date": str(min(row[2] for row in rows)) if rows else None,
        "last_recorded_date": str(max(row[3] for row in rows)) if rows else None,
    })
    return metadata


def comparison_reporting(db, bounds):
    start, end, prior_start, prior_end = bounds
    current = reporting_scope(db, start, end)
    previous = reporting_scope(db, prior_start, prior_end)
    return {
        **current,
        "reporting_date": str(end),
        "current_period": current,
        "previous_period": previous,
        "comparison_available": bool(current["recorded_row_count"] and previous["recorded_row_count"]),
        "comparison_qualification": "Comparison of recorded activity only; historical coverage is unverified.",
    }


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
