from datetime import date, timedelta

import pandas as pd

from analytics_lib import detect_anomalies, detect_recurring


def _tx(rows):
    frame = pd.DataFrame(rows)
    for col, default in (("is_transfer", False), ("is_refund", 0), ("reviewed", 0)):
        if col not in frame.columns:
            frame[col] = default
    return frame


def _row(i, d, amt, merch, cat, reviewed=0):
    return {
        "id": i, "date": d, "amount": amt, "name": merch,
        "effective_merchant": merch, "effective_category": cat, "reviewed": reviewed,
    }


def test_amount_outlier_vs_merchant_history():
    rows = [_row(i, date(2026, 1, i + 1), 5.0, "Cafe", "FOOD/COFFEE") for i in range(6)]
    rows.append(_row(99, date(2026, 3, 1), 80.0, "Cafe", "FOOD/COFFEE"))  # outlier
    an = detect_anomalies(_tx(rows))
    assert list(an["anomaly_type"]) == ["amount_outlier"]
    assert an.iloc[0]["id"] == 99


def test_category_mismatch_vs_dominant():
    rows = [_row(i, date(2026, 1, i + 1), 40.0, "Amazon", "SHOPPING/GENERAL") for i in range(6)]
    rows.append(_row(99, date(2026, 3, 1), 41.0, "Amazon", "FOOD/OTHER"))  # wrong category
    an = detect_anomalies(_tx(rows))
    assert list(an["anomaly_type"]) == ["category_mismatch"]
    assert "usually Shopping" in an.iloc[0]["message"]


def test_large_uncategorized_new_merchant():
    an = detect_anomalies(_tx([_row(1, date(2026, 3, 1), 500.0, "WIRE LLC", "uncategorized")]))
    assert list(an["anomaly_type"]) == ["large_uncategorized"]


def test_small_uncategorized_is_ignored():
    an = detect_anomalies(_tx([_row(1, date(2026, 3, 1), 4.0, "Corner Store", "uncategorized")]))
    assert an.empty


def test_reviewed_rows_are_never_flagged():
    rows = [_row(i, date(2026, 1, i + 1), 5.0, "Cafe", "FOOD/COFFEE") for i in range(6)]
    rows.append(_row(99, date(2026, 3, 1), 80.0, "Cafe", "FOOD/COFFEE", reviewed=1))
    assert detect_anomalies(_tx(rows)).empty


def test_transfers_and_refunds_excluded():
    rows = [_row(1, date(2026, 3, 1), 5000.0, "Big Move", "uncategorized")]
    df = _tx(rows)
    df["is_transfer"] = True
    assert detect_anomalies(df).empty


def test_price_increase_from_recurring():
    rows = [
        _row(i + 1, date(2026, 1, 5) + timedelta(days=30 * i), amt, "News+", "SERVICES/GENERAL")
        for i, amt in enumerate([10.0, 10.0, 10.0, 10.0, 13.0])
    ]
    df = _tx(rows)
    rec = detect_recurring(df)
    an = detect_anomalies(df, rec)
    assert "price_increase" in set(an["anomaly_type"])
    price = an[an["anomaly_type"] == "price_increase"].iloc[0]
    assert price["id"] == 5


def test_routine_rule_categorized_rows_are_quiet():
    # Steady, in-category, unremarkable spend produces no review noise — the whole
    # point of the anomaly surface vs a confirm-everything queue.
    rows = [_row(i, date(2026, 1, i + 1), 40.0 + i, "Amazon", "SHOPPING/GENERAL") for i in range(8)]
    assert detect_anomalies(_tx(rows)).empty


def test_severity_orders_biggest_first():
    rows = [_row(i, date(2026, 1, i + 1), 40.0, "Amazon", "SHOPPING/GENERAL") for i in range(6)]
    rows.append(_row(50, date(2026, 3, 1), 41.0, "Amazon", "FOOD/OTHER"))       # mismatch, sev ~41
    rows.append(_row(51, date(2026, 3, 2), 900.0, "WIRE LLC", "uncategorized"))  # large, sev 900
    an = detect_anomalies(_tx(rows))
    assert an.iloc[0]["id"] == 51
