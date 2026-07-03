from datetime import date, timedelta

import pandas as pd

from analytics_lib import detect_recurring, upcoming_bills


def _tx(rows):
    frame = pd.DataFrame(rows)
    for col in ("is_transfer", "is_refund", "reviewed"):
        if col not in frame.columns:
            frame[col] = 0
    return frame


def _stream(merchant, category, start, step_days, amounts):
    return [
        {
            "id": i + 1,
            "date": start + timedelta(days=step_days * i),
            "amount": amt,
            "name": merchant,
            "effective_merchant": merchant,
            "effective_category": category,
        }
        for i, amt in enumerate(amounts)
    ]


def test_detects_monthly_subscription():
    df = _tx(_stream("Netflix", "FUN/ENTERTAINMENT", date(2026, 1, 10), 30, [15.49] * 6))
    rec = detect_recurring(df)
    assert len(rec) == 1
    row = rec.iloc[0]
    assert row["cadence"] == "monthly"
    assert bool(row["is_subscription"])
    assert row["typical_amount"] == 15.49
    # Next expected charge is one cadence after the last observed one.
    assert row["next_date"] == date(2026, 1, 10) + timedelta(days=30 * 5) + timedelta(days=30)


def test_ignores_irregular_merchant():
    # Random gaps at a grocery store: not a recurring stream.
    dates = [date(2026, 1, 1), date(2026, 1, 3), date(2026, 2, 20), date(2026, 3, 25)]
    rows = [
        {"id": i, "date": d, "amount": 40.0, "name": "Whole Foods",
         "effective_merchant": "Whole Foods", "effective_category": "FOOD/GROCERIES"}
        for i, d in enumerate(dates, 1)
    ]
    assert detect_recurring(_tx(rows)).empty


def test_flags_subscription_price_increase():
    amounts = [12.0, 12.0, 12.0, 12.0, 15.0]  # last charge jumped 25%
    df = _tx(_stream("Spotify", "FUN/ENTERTAINMENT", date(2026, 1, 5), 30, amounts))
    row = detect_recurring(df).iloc[0]
    assert row["price_change_pct"] is not None
    assert round(row["price_change_pct"]) == 25
    assert row["last_amount"] == 15.0


def test_stable_subscription_has_no_price_change():
    df = _tx(_stream("Gym", "HEALTH/FITNESS", date(2026, 1, 5), 30, [40.0] * 6))
    assert detect_recurring(df).iloc[0]["price_change_pct"] is None


def test_transfers_excluded_from_recurring():
    rows = _stream("Payroll Move", "TRANSFER_IN", date(2026, 1, 1), 14, [1000.0] * 6)
    df = _tx(rows)
    df["is_transfer"] = True
    assert detect_recurring(df).empty


def test_upcoming_bills_rolls_stale_dates_forward():
    df = _tx(_stream("Netflix", "FUN/ENTERTAINMENT", date(2026, 1, 10), 30, [15.49] * 6))
    rec = detect_recurring(df)
    # "Today" is well after the last observed charge; the next expected date should
    # be rolled forward into the horizon rather than dropped as stale.
    bills = upcoming_bills(rec, date(2026, 7, 1), horizon_days=31)
    assert len(bills) == 1
    assert bills.iloc[0]["next_date"] >= date(2026, 7, 1) - timedelta(days=30)


def test_upcoming_bills_respects_horizon():
    df = _tx(_stream("Annual", "SERVICES/GENERAL", date(2026, 1, 10), 365, [99.0, 99.0, 99.0]))
    rec = detect_recurring(df)
    # A yearly bill last seen in 2028 is far outside a 14-day horizon.
    assert upcoming_bills(rec, date(2026, 3, 1), horizon_days=14).empty
