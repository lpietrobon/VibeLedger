"""Pure analytical helpers for the dashboard — no Streamlit, no SQLite.

Everything here is a deterministic function over a transactions DataFrame so it
can be unit-tested directly (see tests/test_recurring.py, test_anomalies.py).
The Streamlit/SQLite wrappers (caching, HTTP mutations, chart rendering) live in
dashboard_lib.py and import from this module.

Design note on the review workflow: recurring streams and anomalies are *derived
views*, never stored state. There is no "recurring" or "anomaly" table — they are
recomputed from transactions every load. Dismissal reuses the existing `reviewed`
annotation flag: an anomaly only shows while its transaction is unreviewed, so
marking it reviewed (one API call, already wired) clears it. Adding a new anomaly
type is one function; nothing to migrate.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

import pandas as pd


# --------------------------------------------------------------------------
# Category identity: stable color + icon per top-level category.
#
# One fixed assignment used by EVERY chart and list in the app, so "Food" is the
# same blue everywhere (Copilot's core polish trick). Hues are the validated
# reference categorical palette from the dataviz skill (8 slots, fixed order,
# adjacent CVD ΔE 24.2 in light mode); each top-level spend category is pinned to
# one slot. Income/transfers/uncategorized use reserved neutrals so they never
# impersonate a spend series. Anything past the 8 slots folds to the "Other" gray
# rather than cycling a hue (never cycle — dataviz non-negotiable).
# --------------------------------------------------------------------------
_PALETTE_LIGHT = {
    "blue": "#2a78d6",
    "aqua": "#1baf7a",
    "yellow": "#eda100",
    "green": "#008300",
    "violet": "#4a3aa7",
    "red": "#e34948",
    "magenta": "#e87ba4",
    "orange": "#eb6834",
}
_PALETTE_DARK = {
    "blue": "#3987e5",
    "aqua": "#199e70",
    "yellow": "#c98500",
    "green": "#008300",
    "violet": "#9085e9",
    "red": "#e66767",
    "magenta": "#d55181",
    "orange": "#d95926",
}

# Reserved neutrals (not part of the categorical slots).
_NEUTRAL_LIGHT = "#898781"
_NEUTRAL_DARK = "#898781"
_INCOME_LIGHT = "#0ca30c"  # status "good" — income reads positive
_INCOME_DARK = "#0ca30c"

# top-level category root -> (palette slot, material icon)
_CATEGORY_SLOTS: dict[str, tuple[str, str]] = {
    "FOOD": ("blue", "restaurant"),
    "SHOPPING": ("aqua", "shopping_bag"),
    "TRANSPORT": ("yellow", "directions_car"),
    "HOUSING": ("green", "home"),
    "FUN": ("violet", "celebration"),
    "HEALTH": ("red", "favorite"),
    "SERVICES": ("magenta", "build"),
    "FINANCE": ("orange", "account_balance"),
}
_ICON_FALLBACK = "category"
_SPECIAL_ICONS = {
    "INCOME": "payments",
    "TRANSFER_IN": "swap_horiz",
    "TRANSFER_OUT": "swap_horiz",
    "TRANSFER": "swap_horiz",
    "BANK_FEES": "receipt_long",
    "GOVERNMENT_AND_NON_PROFIT": "volunteer_activism",
    "HOME_IMPROVEMENT": "handyman",
    "UNCATEGORIZED": "help",
}


def category_root(category: str | None) -> str:
    """Top-level category (text before the first '/'), upper-cased and trimmed."""
    if category is None or (isinstance(category, float) and pd.isna(category)):
        return "UNCATEGORIZED"
    root = str(category).split("/", 1)[0].strip().upper()
    return root or "UNCATEGORIZED"


def category_color(category: str | None, dark: bool = False) -> str:
    """Stable hex color for a category, matching in light and dark modes."""
    root = category_root(category)
    if root in _CATEGORY_SLOTS:
        slot = _CATEGORY_SLOTS[root][0]
        return (_PALETTE_DARK if dark else _PALETTE_LIGHT)[slot]
    if root == "INCOME":
        return _INCOME_DARK if dark else _INCOME_LIGHT
    return _NEUTRAL_DARK if dark else _NEUTRAL_LIGHT


def category_icon(category: str | None) -> str:
    """Material Symbols icon name for a category (usable as :material/<name>:)."""
    root = category_root(category)
    if root in _CATEGORY_SLOTS:
        return _CATEGORY_SLOTS[root][1]
    return _SPECIAL_ICONS.get(root, _ICON_FALLBACK)


def category_color_map(categories, dark: bool = False) -> dict[str, str]:
    """Map full category strings to their stable colors for Plotly color_discrete_map."""
    return {str(c): category_color(c, dark) for c in categories}


# --------------------------------------------------------------------------
# Net worth over time (from account balance snapshots).
# --------------------------------------------------------------------------
ASSET_TYPES = {"depository", "investment", "brokerage"}
LIABILITY_TYPES = {"credit", "loan"}


def net_worth_timeseries(snapshots: pd.DataFrame, accounts: pd.DataFrame) -> pd.DataFrame:
    """Build a daily net-worth series from sparse per-account balance snapshots.

    snapshots: columns account_id, as_of_date, current_balance (one row per
    account per sync day). accounts: columns id, type.

    Snapshots are only written on sync days, so each account's balance is
    forward-filled across the date axis; net worth on a given day is the sum of
    asset-type balances minus liability-type balances using the latest known
    balance for every account. Returns columns date, assets, liabilities, net_worth.
    """
    columns = ["date", "assets", "liabilities", "net_worth"]
    if snapshots is None or snapshots.empty:
        return pd.DataFrame(columns=columns)

    snap = snapshots.copy()
    snap["as_of_date"] = pd.to_datetime(snap["as_of_date"]).dt.date
    snap["current_balance"] = pd.to_numeric(snap["current_balance"], errors="coerce")
    types = dict(zip(accounts["id"], accounts["type"])) if not accounts.empty else {}

    wide = snap.pivot_table(
        index="as_of_date", columns="account_id", values="current_balance", aggfunc="last"
    ).sort_index().ffill()

    rows = []
    for as_of, series in wide.iterrows():
        assets = liabilities = 0.0
        for account_id, balance in series.items():
            if pd.isna(balance):
                continue
            account_type = types.get(account_id)
            if account_type in ASSET_TYPES:
                assets += float(balance)
            elif account_type in LIABILITY_TYPES:
                liabilities += float(balance)
        rows.append(
            {"date": as_of, "assets": assets, "liabilities": liabilities,
             "net_worth": assets - liabilities}
        )
    return pd.DataFrame(rows, columns=columns)


# --------------------------------------------------------------------------
# Recurring / subscription detection.
# --------------------------------------------------------------------------
# (name, low_gap, high_gap, canonical_days) — median inter-charge gap in days.
_CADENCES = [
    ("weekly", 5, 9, 7),
    ("biweekly", 11, 17, 14),
    ("monthly", 25, 35, 30),
    ("quarterly", 80, 100, 91),
    ("yearly", 330, 400, 365),
]


def _merchant_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _merchant_series(df: pd.DataFrame) -> pd.Series:
    merchant = df["effective_merchant"] if "effective_merchant" in df.columns else pd.Series("", index=df.index)
    name = df["name"] if "name" in df.columns else pd.Series("", index=df.index)
    return merchant.fillna("").mask(merchant.fillna("").eq(""), name).fillna("")


def _classify_cadence(median_gap: float):
    for name, low, high, days in _CADENCES:
        if low <= median_gap <= high:
            return name, low, high, days
    return None, None, None, None


def _expense_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Non-transfer expense rows (positive amount), refunds excluded."""
    f = df
    if "is_transfer" in f.columns:
        f = f[~f["is_transfer"].fillna(False).astype(bool)]
    if "is_refund" in f.columns:
        f = f[~f["is_refund"].fillna(0).astype(bool)]
    return f[f["amount"] > 0].copy()


def detect_recurring(df: pd.DataFrame, min_occurrences: int = 3) -> pd.DataFrame:
    """Detect regular-cadence merchant streams (subscriptions & bills).

    Returns one row per recurring stream with columns:
      merchant, category, cadence, cadence_days, typical_amount, last_amount,
      prior_amount, last_date, next_date, count, amount_cv, is_subscription,
      price_change_pct, last_txn_id.

    A stream qualifies when it has >= min_occurrences charges at a recognizable
    cadence (weekly..yearly) and at least half the gaps fall inside that cadence
    band. amount_cv is the coefficient of variation of the charge amounts;
    is_subscription flags very stable amounts (cv < 0.12). price_change_pct is the
    latest amount vs the median of the prior amounts (None if unchanged/insufficient
    history) — this is what surfaces "your subscription went up".
    """
    empty = pd.DataFrame(
        columns=[
            "merchant", "category", "cadence", "cadence_days", "typical_amount",
            "last_amount", "prior_amount", "last_date", "next_date", "count",
            "amount_cv", "is_subscription", "price_change_pct", "last_txn_id",
        ]
    )
    expenses = _expense_rows(df)
    if expenses.empty:
        return empty

    expenses = expenses.assign(_key=_merchant_series(expenses).map(_merchant_key))
    expenses = expenses[expenses["_key"] != ""]
    if expenses.empty:
        return empty

    rows: list[dict] = []
    for key, group in expenses.groupby("_key"):
        group = group.sort_values("date")
        if len(group) < min_occurrences:
            continue
        dates = list(group["date"])
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        gaps = [g for g in gaps if g > 0]
        if len(gaps) < min_occurrences - 1:
            continue
        median_gap = float(pd.Series(gaps).median())
        cadence, low, high, days = _classify_cadence(median_gap)
        if cadence is None:
            continue
        in_band = sum(1 for g in gaps if low <= g <= high) / len(gaps)
        if in_band < 0.5:
            continue

        amounts = pd.to_numeric(group["amount"], errors="coerce").dropna()
        typical = float(amounts.median())
        mean_amount = float(amounts.mean())
        amount_cv = float(amounts.std(ddof=0) / mean_amount) if mean_amount else 0.0
        last_amount = float(amounts.iloc[-1])
        prior = amounts.iloc[:-1]
        prior_amount = float(prior.median()) if len(prior) else typical

        price_change_pct = None
        if len(prior) >= 2 and prior_amount:
            delta = (last_amount - prior_amount) / prior_amount * 100
            if abs(delta) >= 10 and abs(last_amount - prior_amount) >= 1.0:
                price_change_pct = delta

        last_date = dates[-1]
        display_merchant = str(_merchant_series(group).iloc[-1])
        category = str(group["effective_category"].fillna("Uncategorized").iloc[-1])
        rows.append(
            {
                "merchant": display_merchant or key.title(),
                "category": category,
                "cadence": cadence,
                "cadence_days": days,
                "typical_amount": typical,
                "last_amount": last_amount,
                "prior_amount": prior_amount,
                "last_date": last_date,
                "next_date": last_date + timedelta(days=days),
                "count": int(len(group)),
                "amount_cv": amount_cv,
                "is_subscription": bool(amount_cv < 0.12),
                # Only treat a jump as a real "price increase" for stable
                # subscriptions; a spike at a variable merchant is an outlier,
                # not a price hike, and is caught by amount_outlier instead.
                "price_change_pct": price_change_pct if amount_cv < 0.20 else None,
                "last_txn_id": int(group["id"].iloc[-1]) if "id" in group.columns else None,
            }
        )

    if not rows:
        return empty
    result = pd.DataFrame(rows)
    return result.sort_values("next_date").reset_index(drop=True)


def upcoming_bills(recurring: pd.DataFrame, today: date, horizon_days: int = 14) -> pd.DataFrame:
    """Recurring streams whose next expected charge lands within the horizon.

    The next_date from detect_recurring can be in the past if a charge is overdue
    (or the stream lapsed); we roll it forward by whole cadence periods so a bill
    that was due yesterday shows as due now, not skipped.
    """
    if recurring.empty:
        return recurring.copy()

    horizon_end = today + timedelta(days=horizon_days)
    rolled = []
    for row in recurring.itertuples():
        next_date = row.next_date
        days = row.cadence_days or 30
        # Roll a stale expected date forward to the next future-ish occurrence.
        while next_date < today - timedelta(days=days):
            next_date = next_date + timedelta(days=days)
        if next_date <= horizon_end:
            rolled.append({**row._asdict(), "next_date": next_date})
    if not rolled:
        return recurring.iloc[0:0].copy()
    out = pd.DataFrame(rolled).drop(columns=["Index"], errors="ignore")
    return out.sort_values("next_date").reset_index(drop=True)


# --------------------------------------------------------------------------
# Anomaly detection — the review surface.
#
# Deliberately NOT a "confirm every transaction" queue. Rules already categorize
# the routine stuff; this only surfaces the handful of things worth a human look:
#   price_increase   a recurring charge went up (subscription price hike)
#   amount_outlier   a charge far above this merchant's usual amount
#   category_mismatch this merchant is usually category X, this one isn't
#   large_uncategorized a big charge with no category and no merchant history
# Only unreviewed, non-transfer, non-refund rows are considered, so marking a row
# reviewed clears it. Each check is one self-contained block — add a type by
# adding a block.
# --------------------------------------------------------------------------
def detect_anomalies(
    df: pd.DataFrame,
    recurring: pd.DataFrame | None = None,
    *,
    min_history: int = 4,
    outlier_ratio: float = 2.5,
    outlier_min_delta: float = 25.0,
    large_uncategorized: float = 100.0,
    dominant_share: float = 0.7,
) -> pd.DataFrame:
    """Return unreviewed transactions worth a look, most impactful first.

    Columns: id, date, merchant, category, amount, anomaly_type, severity, message.
    severity is an approximate dollar impact used only for ranking.
    """
    columns = ["id", "date", "merchant", "category", "amount", "anomaly_type", "severity", "message"]
    if df.empty:
        return pd.DataFrame(columns=columns)

    work = df.copy()
    if "is_transfer" in work.columns:
        work = work[~work["is_transfer"].fillna(False).astype(bool)]
    if "is_refund" in work.columns:
        work = work[~work["is_refund"].fillna(0).astype(bool)]
    if work.empty:
        return pd.DataFrame(columns=columns)

    # Plain (no leading underscore) column names — itertuples() drops those.
    work = work.assign(mkey=_merchant_series(work).map(_merchant_key))
    work["mdisp"] = _merchant_series(work)
    work["mroot"] = work["effective_category"].map(category_root)

    reviewed = (
        work["reviewed"].fillna(0).astype(bool)
        if "reviewed" in work.columns
        else pd.Series(False, index=work.index)
    )

    # Per-merchant history stats over the full (reviewed+unreviewed) expense set,
    # so a merchant's "usual" is learned from everything we've seen.
    expenses = work[work["amount"] > 0]
    merchant_stats: dict[str, dict] = {}
    for key, group in expenses.groupby("mkey"):
        if key == "":
            continue
        amounts = pd.to_numeric(group["amount"], errors="coerce").dropna()
        roots = group["mroot"]
        dominant = roots.value_counts(normalize=True)
        merchant_stats[key] = {
            "count": int(len(group)),
            "median": float(amounts.median()) if len(amounts) else 0.0,
            "dominant_root": str(dominant.index[0]) if len(dominant) else "UNCATEGORIZED",
            "dominant_share": float(dominant.iloc[0]) if len(dominant) else 0.0,
        }

    price_increase_ids: dict[int, dict] = {}
    if recurring is not None and not recurring.empty:
        for row in recurring.itertuples():
            pct = getattr(row, "price_change_pct", None)
            txn_id = getattr(row, "last_txn_id", None)
            if pct is not None and pct > 0 and txn_id is not None:
                price_increase_ids[int(txn_id)] = {
                    "prior": float(row.prior_amount),
                    "last": float(row.last_amount),
                    "pct": float(pct),
                }

    findings: list[dict] = []
    for row in work.itertuples():
        if reviewed.loc[row.Index]:
            continue
        amount = float(row.amount) if pd.notna(row.amount) else 0.0
        if amount <= 0:
            continue  # income/credits handled elsewhere
        merchant = str(row.mdisp) or "(unknown)"
        category = str(getattr(row, "effective_category", "") or "uncategorized")
        root = row.mroot
        txn_id = int(row.id)
        stats = merchant_stats.get(row.mkey)

        # 1. Recurring price increase (highest signal).
        if txn_id in price_increase_ids:
            info = price_increase_ids[txn_id]
            findings.append({
                "id": txn_id, "date": row.date, "merchant": merchant,
                "category": category, "amount": amount, "anomaly_type": "price_increase",
                "severity": (info["last"] - info["prior"]) * 12,  # annualized bump
                "message": (
                    f"{merchant} charged ${info['last']:,.2f}, up from ~${info['prior']:,.2f} "
                    f"(+{info['pct']:.0f}%)"
                ),
            })
            continue

        # 2. Amount outlier vs this merchant's history.
        if stats and stats["count"] >= min_history and stats["median"] > 0:
            median = stats["median"]
            if amount >= median * outlier_ratio and amount - median >= outlier_min_delta:
                findings.append({
                    "id": txn_id, "date": row.date, "merchant": merchant,
                    "category": category, "amount": amount, "anomaly_type": "amount_outlier",
                    "severity": amount - median,
                    "message": (
                        f"${amount:,.2f} at {merchant} — {amount / median:.1f}× the usual "
                        f"~${median:,.2f}"
                    ),
                })
                continue

        # 3. Category mismatch vs this merchant's dominant category.
        if stats and stats["count"] >= min_history and stats["dominant_share"] >= dominant_share:
            dominant_root = stats["dominant_root"]
            if root != dominant_root and dominant_root != "UNCATEGORIZED":
                if root == "UNCATEGORIZED":
                    msg = f"{merchant} is uncategorized here, usually {dominant_root.title()}"
                else:
                    msg = f"{merchant} categorized as {root.title()}, usually {dominant_root.title()}"
                findings.append({
                    "id": txn_id, "date": row.date, "merchant": merchant,
                    "category": category, "amount": amount, "anomaly_type": "category_mismatch",
                    "severity": amount,
                    "message": msg,
                })
                continue

        # 4. Large uncategorized with no merchant history to infer from.
        if root == "UNCATEGORIZED" and amount >= large_uncategorized:
            if not stats or stats["count"] < min_history:
                findings.append({
                    "id": txn_id, "date": row.date, "merchant": merchant,
                    "category": category, "amount": amount, "anomaly_type": "large_uncategorized",
                    "severity": amount,
                    "message": f"Large uncategorized charge: ${amount:,.2f} at {merchant}",
                })
                continue

    if not findings:
        return pd.DataFrame(columns=columns)
    result = pd.DataFrame(findings)[columns]
    return result.sort_values("severity", ascending=False).reset_index(drop=True)


# --------------------------------------------------------------------------
# Insight headlines — one plain-language sentence per chart.
# The #1 practitioner critique of Monarch is charts with no takeaway; every chart
# in this app pairs with a computed sentence built from the same numbers it plots.
# --------------------------------------------------------------------------
def _money(value: float) -> str:
    return f"${value:,.0f}"


def spending_headline(summary: dict, current_label: str, previous_label: str) -> str:
    """Headline for the Spending page from a spending_period_summary() dict."""
    total = summary.get("total", 0.0)
    parts = [f"You've spent {_money(total)} in {current_label}"]
    pct = summary.get("change_pct")
    if pct is not None:
        direction = "more than" if pct >= 0 else "less than"
        parts.append(f"{abs(pct):.0f}% {direction} {previous_label}")
    driver = summary.get("top_driver")
    if driver and driver.get("amount", 0) > 0:
        parts.append(f"led by {driver['category'].title()} ({_money(driver['amount'])})")
    projection = summary.get("projection")
    if projection and projection > total * 1.02:
        parts.append(f"on pace for ~{_money(projection)}")
    return " · ".join(parts) + "."


def cashflow_headline(monthly: pd.DataFrame) -> str:
    """Headline for the Cashflow page from a monthly income/expense/net frame."""
    if monthly.empty:
        return "No cashflow in this window yet."
    latest = monthly.iloc[-1]
    net = float(latest["net"])
    label = str(latest["month"])
    verb = "positive" if net >= 0 else "negative"
    parts = [
        f"{label}: net cashflow {_money(net)} ({verb})",
        f"income {_money(float(latest['income']))} vs expenses {_money(float(latest['expense']))}",
    ]
    if len(monthly) >= 2:
        prev_net = float(monthly.iloc[-2]["net"])
        change = net - prev_net
        arrow = "up" if change >= 0 else "down"
        parts.append(f"{arrow} {_money(abs(change))} vs {monthly.iloc[-2]['month']}")
    return " · ".join(parts) + "."


def net_worth_headline(networth: pd.DataFrame, lookback_days: int = 30) -> str:
    """Headline for a net-worth-over-time frame (columns: date, net_worth)."""
    if networth.empty:
        return "No balance history captured yet — it accrues from each sync."
    networth = networth.sort_values("date")
    latest = networth.iloc[-1]
    current = float(latest["net_worth"])
    cutoff = latest["date"] - timedelta(days=lookback_days)
    prior_rows = networth[networth["date"] <= cutoff]
    base = prior_rows.iloc[-1] if not prior_rows.empty else networth.iloc[0]
    change = current - float(base["net_worth"])
    parts = [f"Net worth is {_money(current)}"]
    if abs(change) >= 1:
        arrow = "up" if change >= 0 else "down"
        pct = (change / abs(float(base["net_worth"])) * 100) if base["net_worth"] else 0.0
        span = (latest["date"] - base["date"]).days or lookback_days
        parts.append(f"{arrow} {_money(abs(change))} ({pct:+.1f}%) over the last {span} days")
    return " · ".join(parts) + "."
