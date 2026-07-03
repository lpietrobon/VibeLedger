from datetime import date

import pandas as pd

from analytics_lib import net_worth_headline, net_worth_timeseries


def test_empty_snapshots():
    assert net_worth_timeseries(pd.DataFrame(), pd.DataFrame()).empty


def test_assets_minus_liabilities_with_forward_fill():
    accounts = pd.DataFrame(
        {"id": [1, 2], "type": ["depository", "credit"]}
    )
    snapshots = pd.DataFrame(
        [
            {"account_id": 1, "as_of_date": "2026-01-01", "current_balance": 1000.0},
            {"account_id": 2, "as_of_date": "2026-01-01", "current_balance": 200.0},
            # Only the checking account is re-snapshotted on Jan 3; the credit
            # balance must forward-fill from Jan 1.
            {"account_id": 1, "as_of_date": "2026-01-03", "current_balance": 1500.0},
        ]
    )
    ts = net_worth_timeseries(snapshots, accounts)
    assert list(ts["date"]) == [date(2026, 1, 1), date(2026, 1, 3)]
    jan1 = ts.iloc[0]
    assert jan1["assets"] == 1000.0 and jan1["liabilities"] == 200.0
    assert jan1["net_worth"] == 800.0
    jan3 = ts.iloc[1]
    assert jan3["assets"] == 1500.0 and jan3["liabilities"] == 200.0  # forward-filled
    assert jan3["net_worth"] == 1300.0


def test_headline_reports_change():
    ts = pd.DataFrame(
        {"date": [date(2026, 5, 1), date(2026, 6, 1)], "net_worth": [100000.0, 105000.0]}
    )
    headline = net_worth_headline(ts, lookback_days=45)
    assert "$105,000" in headline
    assert "up" in headline


def test_headline_handles_no_history():
    assert "No balance history" in net_worth_headline(pd.DataFrame(columns=["date", "net_worth"]))
