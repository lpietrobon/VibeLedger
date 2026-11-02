"""Deterministic, qualified outlier hints over posted daily expense contributions.

The leading transaction percentage is explicitly an UPPER BOUND on attributable
excess, not proof of a counterfactual causal effect.
"""
from collections import defaultdict
from datetime import date, timedelta
from statistics import median


def detect_spikes(rows, start: date, end: date):
    """rows: iterable of (id, date, merchant, signed expense), incl. 35-day lookback.

    All rows must already follow posted-spend/refund/transfer/duplicate semantics.
    """
    if end < start:
        raise ValueError("start must precede end")
    amounts = defaultdict(float)
    charges = defaultdict(list)
    first_recorded = None
    for ident, day, merchant, amount in rows:
        if not start - timedelta(days=35) <= day <= end:
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
        historic = [amounts[day - timedelta(days=n)] for n in range(1, 29)]
        # Sparse posted histories are not verified zero-spend days: abstain.
        # At least half of the previous 28 calendar days must contain
        # positive recorded spending; otherwise zeros may be missing data.
        enough = (first_recorded is not None and first_recorded <= day - timedelta(days=21)
                  and sum(value > 0 for value in historic) >= 14)
        historic_baseline = round(median(historic), 2) if enough else None

        def monthly_match(charge):
            """Heuristic only: the merchant repeats ~monthly, not every few days."""
            _, merchant, amount = charge
            # A daily/weekly merchant whose name and amount match 28 days ago
            # is not a monthly bill. Don't "expect" it twice in the baseline.
            if any(merchant == name for n in range(1, 22)
                   for _, name, _ in charges[day - timedelta(days=n)]):
                return False
            return any(
                merchant == name and abs(amount - previous) <= max(1, amount * 0.1)
                for n in range(27, 35)
                for _, name, previous in charges[day - timedelta(days=n)]
            )

        expected_recurring = [charge for charge in charges[day] if monthly_match(charge)]
        expected_ids = {charge[0] for charge in expected_recurring}
        # Separately account for this day's matched recurring bills. Suppressing
        # the *whole day* would hide an independent large one-time purchase.
        baseline = (
            round(historic_baseline + sum(charge[2] for charge in expected_recurring), 2)
            if historic_baseline is not None else None
        )
        excess = round(observed - baseline, 2) if baseline is not None else None
        is_spike = bool(baseline is not None and excess is not None
                        and observed > 0 and excess >= max(100, abs(historic_baseline) * 1.5)
                        and observed >= baseline + 100)
        candidates = [charge for charge in charges[day] if charge[0] not in expected_ids]
        candidate = max(candidates, key=lambda x: (x[2], -x[0])) if candidates else None
        if is_spike and candidate:
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
                "qualification": ("Largest non-recurring transaction could explain up to this "
                                  "share of excess; baseline is the median of 28 prior "
                                  "calendar days plus matching monthly charges. "
                                  "At least 14 days of positive spend are required for a "
                                  "baseline; recorded history completeness is unverified."),
            })
        day += timedelta(days=1)
    return result
