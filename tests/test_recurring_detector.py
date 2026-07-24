from datetime import date, timedelta
from types import SimpleNamespace

from app.services.recurring_detector import detect_recurring, merchant_key


def _txn(i, d, amount, merchant, name=None, account_id=1, category=None):
    return SimpleNamespace(
        id=i, date=d, amount=amount, merchant_name=merchant,
        name=name or merchant, account_id=account_id, category=category,
    )


def _monthly(merchant, amount, start, count, account_id=1, category=None):
    """A charge on (roughly) the same day of month for `count` months."""
    rows = []
    for k in range(count):
        month = start.month - 1 + k
        year = start.year + month // 12
        d = date(year, month % 12 + 1, start.day)
        rows.append(_txn(len(rows), d, amount, merchant, account_id=account_id, category=category))
    return rows


def test_monthly_subscription_detected():
    txns = _monthly("Netflix", 15.99, date(2026, 1, 15), 6)
    series = detect_recurring(txns, reference_date=date(2026, 7, 1))
    assert len(series) == 1
    s = series[0]
    assert s.cadence == "monthly"
    assert s.occurrences == 6
    assert s.average_amount == 15.99
    assert s.amount_consistent is True
    assert s.status == "active"
    # Median monthly gap is 31 days, so the projection lands one day past the 15th.
    assert s.next_expected_date == date(2026, 7, 16)


def test_weekly_and_yearly_detected():
    weekly = [_txn(i, date(2026, 1, 5) + timedelta(days=7 * i), 4.5, "Gym Locker") for i in range(6)]
    yearly = [_txn(100 + i, date(2024 + i, 3, 2), 99.0, "Domain Renewal") for i in range(3)]
    series = {s.cadence: s for s in detect_recurring(weekly + yearly, reference_date=date(2026, 7, 1))}
    assert set(series) == {"weekly", "yearly"}
    assert series["weekly"].monthly_estimate > series["yearly"].monthly_estimate


def test_irregular_spending_not_flagged():
    # Same merchant, no cadence: gaps of 2, 40, 3, 25 days.
    days = [0, 2, 42, 45, 70]
    txns = [_txn(i, date(2026, 1, 1) + timedelta(days=d), 12.0, "Corner Coffee") for i, d in enumerate(days)]
    assert detect_recurring(txns, reference_date=date(2026, 4, 1)) == []


def test_too_few_occurrences_not_flagged():
    # Two monthly charges is below the monthly minimum (3).
    txns = _monthly("Rare Service", 20.0, date(2026, 1, 10), 2)
    assert detect_recurring(txns, reference_date=date(2026, 4, 1)) == []


def test_inactive_when_last_charge_is_stale():
    txns = _monthly("Old Sub", 9.99, date(2025, 1, 1), 4)  # ends 2025-04
    series = detect_recurring(txns, reference_date=date(2026, 7, 1))
    assert len(series) == 1
    assert series[0].status == "inactive"


def test_variable_amount_still_recurring_but_marked_inconsistent():
    # Utility-style monthly bill with swinging amounts.
    amounts = [80.0, 120.0, 60.0, 140.0]
    txns = [
        _txn(i, date(2026, 1 + i, 5), amt, "City Power")
        for i, amt in enumerate(amounts)
    ]
    series = detect_recurring(txns, reference_date=date(2026, 6, 1))
    assert len(series) == 1
    assert series[0].cadence == "monthly"
    assert series[0].amount_consistent is False


def test_merchant_key_normalizes_store_numbers():
    assert merchant_key(_txn(1, date(2026, 1, 1), 5, "SPOTIFY P0F3A1")) == "spotify"
    assert merchant_key(_txn(1, date(2026, 1, 1), 5, "Spotify")) == "spotify"
