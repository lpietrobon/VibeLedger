from datetime import date

import pandas as pd

from dashboard_lib import overview_period_summary, resolve_date_period


MIN_DATE = date(2024, 1, 1)
MAX_DATE = date(2026, 6, 20)
TODAY = date(2026, 6, 20)


def test_all_time_uses_available_history():
    assert resolve_date_period("All time", TODAY, MIN_DATE, MAX_DATE) == (MIN_DATE, MAX_DATE)


def test_this_and_last_month_are_calendar_periods():
    assert resolve_date_period("This month", TODAY, MIN_DATE, MAX_DATE) == (
        date(2026, 6, 1),
        TODAY,
    )
    assert resolve_date_period("Last month", TODAY, MIN_DATE, MAX_DATE) == (
        date(2026, 5, 1),
        date(2026, 5, 31),
    )


def test_rolling_day_periods_are_inclusive():
    assert resolve_date_period("Last 30 days", TODAY, MIN_DATE, MAX_DATE) == (
        date(2026, 5, 22),
        TODAY,
    )
    assert resolve_date_period("Last 90 days", TODAY, MIN_DATE, MAX_DATE) == (
        date(2026, 3, 23),
        TODAY,
    )


def test_year_periods():
    assert resolve_date_period("This year", TODAY, MIN_DATE, MAX_DATE) == (
        date(2026, 1, 1),
        TODAY,
    )
    assert resolve_date_period("Last year", TODAY, MIN_DATE, MAX_DATE) == (
        date(2025, 1, 1),
        date(2025, 12, 31),
    )


def test_overview_period_summary_compares_spend_and_nets_cashflow():
    df = pd.DataFrame(
        [
            {
                "date": date(2026, 6, 5),
                "amount": 120.0,
                "effective_category": "Food/Groceries",
                "is_refund": False,
            },
            {
                "date": date(2026, 6, 10),
                "amount": -500.0,
                "effective_category": "Income/Salary",
                "is_refund": False,
            },
            {
                "date": date(2026, 5, 8),
                "amount": 80.0,
                "effective_category": "Food/Dining",
                "is_refund": False,
            },
        ]
    )

    result = overview_period_summary(
        df,
        date(2026, 6, 1),
        date(2026, 6, 30),
        date(2026, 5, 1),
        date(2026, 5, 31),
    )

    assert result == {
        "spend": 120.0,
        "previous_spend": 80.0,
        "spend_change": 40.0,
        "income": 500.0,
        "net": 380.0,
        "top_driver": {"category": "Food", "amount": 120.0},
    }
