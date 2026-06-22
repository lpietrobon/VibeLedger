from datetime import date

from dashboard_lib import resolve_date_period


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
