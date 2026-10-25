"""Counterexamples and hand-calculated confidence guards for spike annotations."""
from datetime import date, timedelta

from app.services.timeline_spikes import detect_spikes


def daily_regular(start=date(2026, 9, 1), end=date(2026, 10, 10), amount=200.0):
    rows = []
    day = start
    while day <= end:
        rows.append((len(rows) + 1, day, "ordinary", amount))
        day += timedelta(days=1)
    return rows


def test_recurring_largest_charge_must_not_hide_independent_new_expense():
    rows = daily_regular()
    rows += [
        (1001, date(2026, 9, 10), "Rent", 2300.0),
        (1002, date(2026, 10, 10), "Rent", 2300.0),
        (1003, date(2026, 10, 10), "Urgent dentist", 700.0),
    ]
    annotations = detect_spikes(rows, date(2026, 10, 10), date(2026, 10, 10))
    assert len(annotations) == 1, "A recurring rent charge must not mask an unrelated exceptional purchase"
    assert annotations[0]["top_merchant"] == "Urgent dentist"
    assert annotations[0]["max_attributable_pct"] <= 100.0


def test_7_observed_spend_days_out_of_28_do_not_define_a_reliable_baseline():
    target = date(2026, 10, 10)
    rows = [(i, target - timedelta(days=28 - i), "occasional", 50.0) for i in range(1, 8)]
    rows.append((100, target, "Insurance", 1500.0))
    assert detect_spikes(rows, target, target) == [], "Sparse observation cannot prove all other days were zero"


def test_attribution_stays_a_bounded_excess_upper_limit_with_refund_offsets():
    rows = daily_regular()
    rows += [(2001, date(2026, 10, 10), "Large repair", 2000.0),
             (2002, date(2026, 10, 10), "Refund", -1100.0)]
    annotations = detect_spikes(rows, date(2026, 10, 10), date(2026, 10, 10))
    assert len(annotations) == 1
    spike = annotations[0]
    assert spike["observed"] == 1100.0
    assert spike["baseline"] == 200.0
    assert spike["excess"] == 900.0
    assert spike["max_attributable_amount"] == 900.0
    assert spike["max_attributable_pct"] == 100.0
    assert "up to" in spike["qualification"].lower() or "upper" in spike["qualification"].lower()
