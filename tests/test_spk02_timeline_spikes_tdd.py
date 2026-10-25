from datetime import date, timedelta

from app.services.timeline_spikes import detect_spikes


def fixture(start=date(2026, 9, 1), last=date(2026, 10, 10)):
    rows = []
    d = start
    n = 1
    while d <= last:
        rows.append((n, d, "Everyday purchases", 200.0))
        n += 1
        d += timedelta(days=1)
    return rows


def test_spike_attribution_is_capped_and_transaction_identifiable():
    rows = fixture()
    # Baseline $200, observed $1,200, top expense $850 => max 85% of excess.
    rows += [(10001, date(2026, 10, 10), "Insurance", 850.0),
             (10002, date(2026, 10, 10), "One-off", 150.0)]
    spikes = detect_spikes(rows, date(2026, 10, 8), date(2026, 10, 10))
    assert len(spikes) == 1
    assert spikes[0]["date"] == "2026-10-10"
    assert spikes[0]["observed"] == 1200.0
    assert spikes[0]["baseline"] == 200.0
    assert spikes[0]["excess"] == 1000.0
    assert spikes[0]["top_merchant"] == "Insurance"
    assert spikes[0]["top_transaction_id"] == 10001
    assert spikes[0]["max_attributable_pct"] == 85.0


def test_sparse_history_abstains_instead_of_inventing_zero_baseline():
    assert detect_spikes([(1, date(2026, 10, 10), "Insurance", 3000)],
                         date(2026, 10, 10), date(2026, 10, 10)) == []


def test_negative_refunds_offset_observed_spend_and_ratio_is_bounded():
    rows = fixture()
    rows += [(1001, date(2026, 10, 10), "Charge", 2000),
             (1002, date(2026, 10, 10), "Refund", -1100)]
    spikes = detect_spikes(rows, date(2026, 10, 10), date(2026, 10, 10))
    assert spikes[0]["observed"] == 1100.0
    assert spikes[0]["excess"] == 900.0
    assert spikes[0]["max_attributable_pct"] == 100.0


def test_recurring_monthly_expense_does_not_flag_as_new_spike():
    rows = fixture()
    rows.extend([(200, date(2026, 9, 10), "Rent", 2300),
                 (201, date(2026, 10, 10), "Rent", 2300)])
    assert detect_spikes(rows, date(2026, 10, 10), date(2026, 10, 10)) == []
