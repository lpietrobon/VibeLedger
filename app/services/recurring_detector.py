"""Deterministic detection of recurring / subscription payments.

Groups expense transactions by a normalized merchant key and looks for a regular
cadence (weekly, biweekly, monthly, quarterly, yearly) in the spacing between
occurrences. The logic is pure and side-effect free so it can be unit tested
without a database — the API layer (app/api/routes.py) is responsible for
loading transactions and excluding transfers/refunds before calling in here.

Precedence of the detection is intentionally conservative: a series only counts
as recurring when it has enough occurrences *and* most of the gaps between them
agree with a single cadence. Random, bursty spending at a merchant (a coffee
shop visited on no schedule) fails the regularity check and is dropped.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Protocol


class RecurringTxnLike(Protocol):
    id: int
    date: date
    amount: float
    name: str | None
    merchant_name: str | None
    account_id: int | None
    category: str | None


@dataclass(frozen=True)
class CadenceSpec:
    name: str
    nominal_days: float
    low: int
    high: int
    min_occurrences: int


# Ordered from shortest to longest. `low`/`high` bound the acceptable gap (in
# days) between consecutive occurrences; `min_occurrences` is how many charges
# we require before trusting the pattern (longer cadences need fewer samples
# because history rarely spans many years).
CADENCES: tuple[CadenceSpec, ...] = (
    CadenceSpec("weekly", 7, 6, 8, 4),
    CadenceSpec("biweekly", 14, 12, 16, 3),
    CadenceSpec("monthly", 30.44, 26, 35, 3),
    CadenceSpec("quarterly", 91.31, 84, 98, 2),
    CadenceSpec("yearly", 365.25, 350, 386, 2),
)

# Fraction of consecutive gaps that must fall inside a cadence window for the
# series to count as regular.
_REGULARITY_THRESHOLD = 0.5
# A series is "active" if its most recent charge is no older than this multiple
# of the cadence relative to the reference date.
_ACTIVE_SLACK = 1.5
# Amounts are "consistent" (fixed-price subscription) when their spread around
# the median stays within this fraction.
_AMOUNT_TOLERANCE = 0.2


@dataclass(frozen=True)
class RecurringSeries:
    merchant_key: str
    merchant_label: str
    cadence: str
    occurrences: int
    average_amount: float
    min_amount: float
    max_amount: float
    amount_consistent: bool
    first_date: date
    last_date: date
    next_expected_date: date
    median_interval_days: float
    monthly_estimate: float
    annual_estimate: float
    status: str
    category: str | None
    account_ids: list[int]
    sample_transaction_ids: list[int]


def merchant_key(txn: RecurringTxnLike) -> str:
    """Normalize a transaction to a grouping key.

    Prefers Plaid's cleaned ``merchant_name``; falls back to the raw descriptor.
    Non-alphanumeric characters and trailing digit runs (store numbers, order
    ids) are stripped so "SPOTIFY P0F3A1" and "Spotify" collapse together.
    """
    raw = (txn.merchant_name or txn.name or "").lower()
    tokens = re.split(r"[^a-z0-9]+", raw)
    alpha_tokens = [tok for tok in tokens if tok and not any(c.isdigit() for c in tok)]
    return "".join(alpha_tokens)


def _label_for(txns: list[RecurringTxnLike]) -> str:
    names = [t.merchant_name or t.name for t in txns if (t.merchant_name or t.name)]
    if not names:
        return "(unknown)"
    return Counter(names).most_common(1)[0][0]


def _category_for(txns: list[RecurringTxnLike]) -> str | None:
    cats = [getattr(t, "category", None) for t in txns if getattr(t, "category", None)]
    if not cats:
        return None
    return Counter(cats).most_common(1)[0][0]


def _match_cadence(unique_dates: list[date]) -> tuple[CadenceSpec, float] | None:
    gaps = [(b - a).days for a, b in zip(unique_dates, unique_dates[1:])]
    if not gaps:
        return None
    median_gap = statistics.median(gaps)
    for spec in CADENCES:
        if not (spec.low <= median_gap <= spec.high):
            continue
        if len(unique_dates) < spec.min_occurrences:
            continue
        in_window = sum(1 for g in gaps if spec.low <= g <= spec.high)
        if in_window / len(gaps) >= _REGULARITY_THRESHOLD:
            return spec, median_gap
    return None


def _analyze_group(
    txns: list[RecurringTxnLike], reference_date: date
) -> RecurringSeries | None:
    unique_dates = sorted({t.date for t in txns})
    matched = _match_cadence(unique_dates)
    if not matched:
        return None
    spec, median_gap = matched

    amounts = sorted(float(t.amount) for t in txns)
    average_amount = statistics.mean(amounts)
    median_amount = statistics.median(amounts)
    spread = max(abs(amounts[0] - median_amount), abs(amounts[-1] - median_amount))
    amount_consistent = bool(median_amount) and spread <= _AMOUNT_TOLERANCE * abs(median_amount)

    first_date, last_date = unique_dates[0], unique_dates[-1]
    interval = median_gap or spec.nominal_days
    next_expected = last_date + timedelta(days=round(interval))
    days_since_last = (reference_date - last_date).days
    status = "active" if days_since_last <= spec.high * _ACTIVE_SLACK else "inactive"

    monthly_estimate = average_amount * (30.44 / spec.nominal_days)
    annual_estimate = average_amount * (365.25 / spec.nominal_days)

    return RecurringSeries(
        merchant_key=merchant_key(txns[0]),
        merchant_label=_label_for(txns),
        cadence=spec.name,
        occurrences=len(txns),
        average_amount=round(average_amount, 2),
        min_amount=round(amounts[0], 2),
        max_amount=round(amounts[-1], 2),
        amount_consistent=amount_consistent,
        first_date=first_date,
        last_date=last_date,
        next_expected_date=next_expected,
        median_interval_days=round(median_gap, 1),
        monthly_estimate=round(monthly_estimate, 2),
        annual_estimate=round(annual_estimate, 2),
        status=status,
        category=_category_for(txns),
        account_ids=sorted({t.account_id for t in txns if t.account_id is not None}),
        sample_transaction_ids=[t.id for t in sorted(txns, key=lambda t: t.date, reverse=True)][:6],
    )


def detect_recurring(
    transactions: Iterable[RecurringTxnLike],
    *,
    reference_date: date | None = None,
) -> list[RecurringSeries]:
    """Return detected recurring series, most expensive (monthly-normalized) first.

    Callers should pass expense-side transactions only, with transfers and
    refunds already excluded. Grouping is by normalized merchant, so a merchant
    billed on two unrelated cadences will still be reported as its dominant one.
    """
    reference_date = reference_date or date.today()

    groups: dict[str, list[RecurringTxnLike]] = {}
    for txn in transactions:
        key = merchant_key(txn)
        if not key:
            continue
        groups.setdefault(key, []).append(txn)

    series = [
        result
        for members in groups.values()
        if (result := _analyze_group(members, reference_date)) is not None
    ]
    series.sort(key=lambda s: (-s.monthly_estimate, s.merchant_label))
    return series
