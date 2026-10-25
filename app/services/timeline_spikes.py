"""Deterministic, qualified outlier hints over posted daily expense contributions.

The leading transaction percentage is explicitly an UPPER BOUND on attributable
excess, not proof of a counterfactual causal effect.
"""
from collections import defaultdict
from datetime import date, timedelta
from statistics import median


def detect_spikes(rows, start: date, end: date):
    """rows: iterable of (id, date, merchant, signed expense), incl. 28-day lookback.

    All rows must already follow posted-spend/refund/transfer/duplicate semantics.
    """
    if end < start:
        raise ValueError("start must precede end")
    amounts = defaultdict(float)
    charges = defaultdict(list)
    first_recorded = None
    for ident, day, merchant, amount in rows:
        if not start - timedelta(days=28) <= day <= end:
            continue
        first_recorded = min(first_recorded, day) if first_recorded else day
        amount = round(float(amount or 0), 2)
        amounts[day] += amount
        if amount > 0:
            charges[day].append((int(ident), str(merchant or "Unknown merchant"), amount))
    result = []
    day = start
    while day <= end:
        observed = round(amounts[day], 2)
        # Do not interpret absence of recorded activity as verified zero history.
        enough = first_recorded is not None and first_recorded <= day - timedelta(days=21)
        historic = [amounts[day - timedelta(days=n)] for n in range(1, 29)]
        baseline = round(median(historic), 2) if enough else None
        excess = round(observed - baseline, 2) if baseline is not None else None
        is_spike = bool(baseline is not None and excess is not None
                        and observed > 0 and excess >= max(100, abs(baseline) * 1.5)
                        and observed >= max(150, baseline * 2))
        candidate = max(charges[day], key=lambda x: (x[2], -x[0])) if charges[day] else None
        # Monthly recurring transactions with matching name and approximate date
        # should not be flagged just because a daily median is small.
        recurring = False
        if candidate:
            for days_back in range(27, 35):
                previous = day - timedelta(days=days_back)
                for _, name, amount in charges[previous]:
                    if name == candidate[1] and abs(amount - candidate[2]) <= max(1, candidate[2] * 0.1):
                        recurring = True
                        break
                if recurring:
                    break
        if is_spike and not recurring:
            top = candidate
            cap = round(min(top[2], excess), 2) if top else 0.0
            result.append({
                "date": day.isoformat(),
                "observed": observed, "baseline": baseline, "excess": excess,
                "top_transaction_id": top[0] if top else None,
                "top_merchant": top[1] if top else None,
                "top_amount": top[2] if top else None,
                "max_attributable_amount": cap,
                "max_attributable_pct": round(100 * cap / excess, 1) if excess > 0 else None,
                "qualification": "Largest transaction could explain up to this share of excess; baseline is the median of 28 prior recorded calendar days, with missing days treated as zero. Historic coverage is unverified.",
            })
        day += timedelta(days=1)
    return result
