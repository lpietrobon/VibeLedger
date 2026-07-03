"""Shared helpers for the multipage Streamlit dashboard.

Heavy reads hit SQLite directly (cached via st.cache_data). Mutations go through
the FastAPI server — see api_post/api_delete — so auth middleware and write-path
logic are exercised end-to-end.
"""
from __future__ import annotations

import os
import calendar
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# Pure analytical helpers live in analytics_lib (no Streamlit dependency, so they
# unit-test without the dashboard extra). Re-exported here so pages keep a single
# import surface.
from analytics_lib import (  # noqa: F401
    category_color,
    category_color_map,
    category_icon,
    category_root,
    cashflow_headline,
    detect_anomalies,
    detect_recurring,
    net_worth_headline,
    net_worth_timeseries,
    spending_headline,
    upcoming_bills,
)


DEFAULT_DB = os.environ.get("VIBELEDGER_DB", str(Path.home() / ".vibeledger" / "vibeledger.db"))
DEFAULT_API = os.environ.get("VIBELEDGER_API", "http://127.0.0.1:8000")
ENV_FILE = Path(__file__).resolve().parent / ".env"


def compact_page() -> None:
    """Apply shared compact spacing, especially on phone-sized screens."""
    st.markdown(
        """
        <style>
        .block-container { padding-top: 2.2rem; padding-bottom: 2rem; }
        h1 { font-size: 1.85rem; margin: 0 0 .35rem; }
        h2 { font-size: 1.35rem; margin: .9rem 0 .3rem; }
        h3 { margin: .7rem 0 .25rem; }
        [data-testid="stSidebar"] .block-container { padding-top: 1rem; }
        [data-testid="stHeader"] { height: 2.4rem; background: transparent; }
        @media (max-width: 768px) {
            .block-container { padding: .55rem .7rem 1.25rem; max-width: 100%; }
            h1 { font-size: 1.45rem; line-height: 1.15; margin-bottom: .2rem; }
            h2 { font-size: 1.15rem; line-height: 1.2; margin: .55rem 0 .2rem; }
            h3 { font-size: 1rem; margin: .45rem 0 .15rem; }
            [data-testid="stVerticalBlock"] { gap: .5rem; }
            [data-testid="stMetric"] { padding: .25rem 0; }
            [data-testid="stPlotlyChart"] { margin-top: -.35rem; }
            div[data-testid="stForm"] { padding: .65rem; }
            .stCaptionContainer { margin-bottom: .15rem; }
            button { min-height: 2.5rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_app_navigation() -> None:
    """Render task-based navigation and keep operational tools secondary."""
    with st.sidebar:
        st.markdown("### VibeLedger")
        st.page_link("Spend.py", label="Overview", icon=":material/home:")
        # Inbox-zero review badge: appears only while something needs a look, and
        # disappears when the queue is empty (the daily "cleared it" payoff).
        count = review_count(st.session_state.get("db_path") or DEFAULT_DB)
        if count:
            st.page_link(
                "pages/6_Transactions.py",
                label=f"{count} to review",
                icon=":material/priority_high:",
            )
        st.page_link("pages/6_Transactions.py", label="Transactions", icon=":material/receipt_long:")
        st.page_link("pages/2_Spending.py", label="Spending", icon=":material/donut_small:")
        st.page_link("pages/2_Cashflow.py", label="Cashflow", icon=":material/swap_vert:")
        st.page_link("pages/8_Recurring.py", label="Recurring", icon=":material/event_repeat:")
        st.page_link("pages/1_Accounts.py", label="Accounts", icon=":material/account_balance:")
        with st.expander("More", expanded=False):
            st.page_link("pages/3_Cashflow_Sankey.py", label="Flow")
            st.page_link("pages/0_Transfers.py", label="Transfers")
            st.page_link("pages/5_Rules.py", label="Rules")
            st.page_link("pages/4_Experimental.py", label="Experimental")


@st.cache_data(ttl=60)
def review_count(db_path: str) -> int:
    """Number of transactions currently flagged as anomalies (drives the nav badge)."""
    try:
        df = load_transactions(db_path)
        if df.empty:
            return 0
        return int(len(detect_anomalies(df, detect_recurring(df))))
    except Exception:
        return 0


def api_token() -> str | None:
    tok = os.environ.get("VIBELEDGER_API_TOKEN")
    if tok:
        return tok
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if line.startswith("VIBELEDGER_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip("'\"")
    return None


def _headers() -> dict:
    tok = api_token()
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def api_post(path: str, json: dict | None = None, base: str | None = None) -> requests.Response:
    url = (base or DEFAULT_API).rstrip("/") + path
    return requests.post(url, json=json or {}, headers=_headers(), timeout=30)


def api_delete(path: str, base: str | None = None) -> requests.Response:
    url = (base or DEFAULT_API).rstrip("/") + path
    return requests.delete(url, headers=_headers(), timeout=30)


def api_get(path: str, params: dict | None = None, base: str | None = None) -> requests.Response:
    url = (base or DEFAULT_API).rstrip("/") + path
    return requests.get(url, params=params or {}, headers=_headers(), timeout=30)


def api_patch(path: str, json: dict | None = None, base: str | None = None) -> requests.Response:
    url = (base or DEFAULT_API).rstrip("/") + path
    return requests.patch(url, json=json or {}, headers=_headers(), timeout=30)


def extract_error_message(resp: requests.Response) -> str:
    try:
        body = resp.json()
    except Exception:
        return resp.text.strip() or "Unknown error"

    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(str(x) for x in item.get("loc", []))
                msg = item.get("msg")
                if loc and msg:
                    parts.append(f"{loc}: {msg}")
                elif msg:
                    parts.append(str(msg))
            else:
                parts.append(str(item))
        if parts:
            return "; ".join(parts)
    if isinstance(body, dict):
        return body.get("message") or body.get("error") or str(body)
    return str(body)


@st.cache_data(ttl=60)
def load_transactions(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    try:
        # All COALESCE/effective-field logic lives in the effective_transactions
        # view (defined in schema_patches.py). Add new correctable fields there.
        q = """
        SELECT et.*,
               tp_out.id AS pair_as_out, tp_in.id AS pair_as_in
        FROM effective_transactions et
        LEFT JOIN transfer_pairs tp_out ON tp_out.txn_out_id = et.id
        LEFT JOIN transfer_pairs tp_in  ON tp_in.txn_in_id  = et.id
        """
        df = pd.read_sql_query(q, conn)
    finally:
        conn.close()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["is_transfer"] = (
            df["pair_as_out"].notna() | df["pair_as_in"].notna() | (df["is_transfer_override"] == 1)
        )
    return df


@st.cache_data(ttl=60)
def load_accounts(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT a.id, a.name, a.nickname,
                   COALESCE(a.nickname, a.name || ' \xb7\xb7' || a.mask) AS effective_account_name,
                   a.mask, a.type, a.subtype,
                   a.current_balance, a.available_balance, a.credit_limit, a.currency,
                   i.institution_name
            FROM accounts a
            LEFT JOIN items i ON i.id=a.item_id
            """,
            conn,
        )
    finally:
        conn.close()
    return df


@st.cache_data(ttl=60)
def load_transfer_pairs(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT p.id, p.detected_by, p.confirmed,
                   p.txn_out_id, tout.date AS out_date, tout.amount AS amount,
                   aout.name AS out_account,
                   p.txn_in_id, tin.date AS in_date, ain.name AS in_account
            FROM transfer_pairs p
            JOIN transactions tout ON tout.id=p.txn_out_id
            JOIN transactions tin ON tin.id=p.txn_in_id
            LEFT JOIN accounts aout ON aout.id=tout.account_id
            LEFT JOIN accounts ain ON ain.id=tin.account_id
            ORDER BY tout.date DESC
            """,
            conn,
        )
    finally:
        conn.close()
    return df


@st.cache_data(ttl=60)
def load_balance_snapshots(db_path: str) -> pd.DataFrame:
    """Daily per-account balance snapshots written by each sync."""
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT account_id, as_of_date, current_balance, available_balance
            FROM account_balance_snapshots
            ORDER BY as_of_date
            """,
            conn,
        )
    except Exception:
        # Table may not exist on a very old DB; treat as no history.
        return pd.DataFrame(columns=["account_id", "as_of_date", "current_balance", "available_balance"])
    finally:
        conn.close()
    return df


def md_dollars(text: str) -> str:
    r"""Escape '$' for st.markdown, which otherwise reads a '$...$' pair as LaTeX math."""
    return text.replace("$", r"\$")


def is_dark_theme() -> bool:
    """Best-effort read of the configured Streamlit theme, for chart palettes."""
    try:
        return (st.get_option("theme.base") or "light").lower() == "dark"
    except Exception:
        return False


def sidebar_filters(df: pd.DataFrame):
    """Shared sidebar: data filters (exclude transfers, date range, accounts).

    DB path is a technical/connection setting, not a data filter — it's
    rendered separately by tech_sidebar(), which pages call after all
    filters (including page-specific ones) to keep it at the bottom.
    """
    st.sidebar.header("Filters")
    db_path = st.session_state.get("db_path", DEFAULT_DB)

    if df.empty:
        return db_path, None, None, [], True

    exclude_transfers = st.sidebar.checkbox("Exclude transfers", value=True, key="excl_xfer")

    min_d, max_d = df["date"].min(), df["date"].max()
    period = st.sidebar.selectbox(
        "Period",
        [
            "All time",
            "This month",
            "Last month",
            "Last 30 days",
            "Last 90 days",
            "This year",
            "Last year",
            "Custom range",
        ],
        key="date_period",
    )
    if period == "Custom range":
        custom_range = st.sidebar.date_input(
            "Date range",
            (min_d, max_d),
            min_value=min_d,
            max_value=max_d,
            key="custom_date_range",
        )
        if isinstance(custom_range, (tuple, list)) and len(custom_range) == 2:
            start_d, end_d = custom_range
        else:
            start_d = end_d = custom_range[0] if isinstance(custom_range, (tuple, list)) else custom_range
    else:
        start_d, end_d = resolve_date_period(period, date.today(), min_d, max_d)

    acct_col = "effective_account_name" if "effective_account_name" in df.columns else "account_name"
    accounts = sorted(df[acct_col].fillna("Unknown").unique().tolist())
    selected = st.sidebar.multiselect("Accounts", accounts, default=accounts, key="accounts")

    return db_path, start_d, end_d, selected, exclude_transfers


def tech_sidebar(show_api: bool = True) -> tuple[str, str | None]:
    """Render DB path (and optionally API base) at the bottom of the sidebar.

    Call this last, after sidebar_filters() and any page-specific filters,
    so connection settings stay separated from data filters.
    """
    st.sidebar.divider()
    with st.sidebar.expander("Connection settings", expanded=False):
        db_path = st.text_input("DB path", DEFAULT_DB, key="db_path")
        api_base = st.text_input("API base", DEFAULT_API, key="api_base") if show_api else None
    return db_path, api_base


def resolve_date_period(period: str, today: date, min_d: date, max_d: date) -> tuple[date, date]:
    """Resolve a sidebar period preset without discarding comparison history."""
    if period == "This month":
        return today.replace(day=1), today
    if period == "Last month":
        end = today.replace(day=1) - timedelta(days=1)
        return end.replace(day=1), end
    if period == "Last 30 days":
        return today - timedelta(days=29), today
    if period == "Last 90 days":
        return today - timedelta(days=89), today
    if period == "This year":
        return date(today.year, 1, 1), today
    if period == "Last year":
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    return min_d, max_d


def apply_scope_filters(df: pd.DataFrame, accounts, exclude_transfers: bool) -> pd.DataFrame:
    """Apply non-date filters, preserving history for comparison charts."""
    f = df.copy()
    if accounts:
        acct_col = "effective_account_name" if "effective_account_name" in f.columns else "account_name"
        f = f[f[acct_col].fillna("Unknown").isin(accounts)]
    if exclude_transfers and "is_transfer" in f.columns:
        f = f[~f["is_transfer"]]
    return f


def apply_date_filter(df: pd.DataFrame, start_d, end_d) -> pd.DataFrame:
    f = df.copy()
    if start_d is not None:
        f = f[(f["date"] >= start_d) & (f["date"] <= end_d)]
    return f


def apply_filters(df: pd.DataFrame, start_d, end_d, accounts, exclude_transfers: bool) -> pd.DataFrame:
    return apply_date_filter(
        apply_scope_filters(df, accounts, exclude_transfers),
        start_d,
        end_d,
    )


def parse_transaction_filter_query(raw: str) -> list[dict]:
    """Parse the power-user transaction query into reusable filter tokens."""
    filters: list[dict] = []
    text_parts: list[str] = []
    for token in raw.strip().split():
        if match := re.match(r"^(?:cat|category):(.+)$", token, re.I):
            filters.append({"type": "category", "value": match.group(1), "label": f"cat: {match.group(1)}"})
        elif match := re.match(r"^(?:amount:)?[>≥](\d+(?:\.\d+)?)$", token):
            value = float(match.group(1))
            filters.append({"type": "amount_min", "value": value, "label": f"≥ ${value:,.0f}"})
        elif match := re.match(r"^(?:amount:)?[<≤](\d+(?:\.\d+)?)$", token):
            value = float(match.group(1))
            filters.append({"type": "amount_max", "value": value, "label": f"≤ ${value:,.0f}"})
        elif match := re.match(r"^from:(\d{4}-\d{2}(?:-\d{2})?)$", token, re.I):
            filters.append({"type": "date_from", "value": match.group(1), "label": f"from {match.group(1)}"})
        elif match := re.match(r"^to:(\d{4}-\d{2}(?:-\d{2})?)$", token, re.I):
            filters.append({"type": "date_to", "value": match.group(1), "label": f"to {match.group(1)}"})
        elif match := re.match(r"^account:(.+)$", token, re.I):
            filters.append({"type": "account", "value": match.group(1), "label": f"account: {match.group(1)}"})
        elif re.match(r"^uncat(?:egorized)?$", token, re.I):
            filters.append({"type": "uncategorized", "value": True, "label": "uncategorized only"})
        else:
            text_parts.append(token)
    if text_parts:
        text_value = " ".join(text_parts)
        filters.append({"type": "text", "value": text_value, "label": f'"{text_value}"'})
    return filters


def apply_transaction_filter_tokens(
    df: pd.DataFrame,
    filters: list[dict],
    *,
    skip_dates: bool = False,
) -> pd.DataFrame:
    """Apply parsed transaction filters consistently across dashboard pages."""
    filtered = df.copy()
    for item in filters:
        filter_type, value = item["type"], item["value"]
        if skip_dates and filter_type in {"date_from", "date_to"}:
            continue
        if filter_type == "text":
            term = str(value).lower()
            filtered = filtered[
                filtered["name"].fillna("").str.lower().str.contains(term, regex=False)
                | filtered["effective_merchant"].fillna("").str.lower().str.contains(term, regex=False)
            ]
        elif filter_type == "category":
            category = str(value).lower()
            category_values = filtered["effective_category"].fillna("").str.lower()
            filtered = filtered[(category_values == category) | category_values.str.startswith(category + "/")]
        elif filter_type == "amount_min":
            filtered = filtered[filtered["amount"] >= value]
        elif filter_type == "amount_max":
            filtered = filtered[filtered["amount"] <= value]
        elif filter_type == "date_from":
            parts = [int(part) for part in str(value).split("-")]
            boundary = date(*parts) if len(parts) == 3 else date(parts[0], parts[1], 1)
            filtered = filtered[filtered["date"] >= boundary]
        elif filter_type == "date_to":
            parts = [int(part) for part in str(value).split("-")]
            boundary = (
                date(*parts)
                if len(parts) == 3
                else date(parts[0], parts[1], calendar.monthrange(parts[0], parts[1])[1])
            )
            filtered = filtered[filtered["date"] <= boundary]
        elif filter_type == "account":
            account_col = "effective_account_name" if "effective_account_name" in filtered.columns else "account_name"
            filtered = filtered[
                filtered[account_col].fillna("").str.lower().str.contains(str(value).lower(), regex=False)
            ]
        elif filter_type == "uncategorized":
            filtered = filtered[
                filtered["effective_category"].fillna("uncategorized").str.lower().eq("uncategorized")
            ]
    return filtered


def spend_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Expense-side rows, including negative refunds that reduce spend."""
    is_refund = (
        df["is_refund"].fillna(0).astype(bool)
        if "is_refund" in df.columns
        else pd.Series(False, index=df.index)
    )
    return df[(df["amount"] > 0) | is_refund].copy()


def add_cashflow_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add signed expense and positive income columns with refunds netted to spend."""
    out = df.copy()
    is_refund = (
        out["is_refund"].fillna(0).astype(bool)
        if "is_refund" in out.columns
        else pd.Series(False, index=out.index)
    )
    out["expense"] = out["amount"].where((out["amount"] > 0) | is_refund, 0)
    out["income"] = (-out["amount"]).where((out["amount"] < 0) & ~is_refund, 0)
    return out


def overview_period_summary(
    df: pd.DataFrame,
    current_start: date,
    current_end: date,
    previous_start: date,
    previous_end: date,
) -> dict:
    """Return current/previous spend, income, net, and top spending driver."""
    scoped = add_cashflow_columns(df)
    current = scoped[(scoped["date"] >= current_start) & (scoped["date"] <= current_end)]
    previous = scoped[(scoped["date"] >= previous_start) & (scoped["date"] <= previous_end)]

    current_spend = float(current["expense"].sum())
    previous_spend = float(previous["expense"].sum())
    current_income = float(current["income"].sum())
    current_net = current_income - current_spend

    top_driver = None
    if not current.empty:
        category = (
            current.assign(
                overview_category=current["effective_category"]
                .fillna("Uncategorized")
                .astype(str)
                .str.split("/")
                .str[0]
                .str.strip()
                .replace("", "Uncategorized")
            )
            .groupby("overview_category")["expense"]
            .sum()
            .sort_values(ascending=False)
        )
        if not category.empty and float(category.iloc[0]) > 0:
            top_driver = {"category": str(category.index[0]), "amount": float(category.iloc[0])}

    return {
        "spend": current_spend,
        "previous_spend": previous_spend,
        "spend_change": current_spend - previous_spend,
        "income": current_income,
        "net": current_net,
        "top_driver": top_driver,
    }


def spending_period_summary(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    *,
    elapsed_days: int,
    total_days: int,
) -> dict:
    """Summarize period spend, comparison, pace projection, and top category."""
    current_total = float(current["amount"].sum()) if not current.empty else 0.0
    previous_total = float(previous["amount"].sum()) if not previous.empty else 0.0
    projection = current_total
    if elapsed_days > 0 and total_days > elapsed_days:
        projection = current_total / elapsed_days * total_days

    top_driver = None
    if not current.empty:
        category = (
            current["effective_category"]
            .fillna("Uncategorized")
            .astype(str)
            .str.split("/")
            .str[0]
            .str.strip()
            .replace("", "Uncategorized")
        )
        totals = (
            current.assign(summary_category=category)
            .groupby("summary_category")["amount"]
            .sum()
            .sort_values(ascending=False)
        )
        if not totals.empty:
            top_driver = {"category": str(totals.index[0]), "amount": float(totals.iloc[0])}

    return {
        "total": current_total,
        "previous_total": previous_total,
        "change": current_total - previous_total,
        "change_pct": (
            (current_total - previous_total) / previous_total * 100
            if previous_total
            else None
        ),
        "projection": projection,
        "top_driver": top_driver,
    }


def period_bounds_n(granularity: str, today, n_periods: int = 4) -> list[dict]:
    """Return n_periods period dicts for 'monthly' or 'yearly' granularity, most recent first.

    Each dict has "start", "end", "len" (day-of-period of the last day, used as
    the x-axis range for cumulative charts) and "label" (e.g. "Jun 2026" or "2026").
    The current (i=0) period runs up to `today`; earlier periods run to their
    natural end (end of month / end of year).
    """
    import calendar

    periods = []
    if granularity == "yearly":
        for i in range(n_periods):
            year = today.year - i
            start = date(year, 1, 1)
            if i == 0:
                end = today
                length = end.timetuple().tm_yday
            else:
                end = date(year, 12, 31)
                length = 366 if calendar.isleap(year) else 365
            periods.append({"start": start, "end": end, "len": length, "label": str(year)})
    else:
        anchor_year, anchor_month = today.year, today.month
        for i in range(n_periods):
            month = anchor_month - i
            year = anchor_year
            while month <= 0:
                month += 12
                year -= 1
            start = date(year, month, 1)
            days_in_month = calendar.monthrange(year, month)[1]
            if i == 0:
                end = today
                length = today.day
            else:
                end = date(year, month, days_in_month)
                length = days_in_month
            periods.append({
                "start": start,
                "end": end,
                "len": length,
                "label": f"{calendar.month_abbr[month]} {year}",
            })
    return periods


def cumulative_series(period_df: pd.DataFrame, granularity: str, max_x: int) -> pd.DataFrame:
    """Group amounts by day-of-month or day-of-year, reindex to 1..max_x, and cumsum.

    Returns a DataFrame with columns "x" and "cumulative".
    """
    if period_df.empty:
        daily = pd.Series(dtype=float)
    elif granularity == "yearly":
        daily = period_df.groupby(period_df["date"].apply(lambda d: d.timetuple().tm_yday))["amount"].sum()
    else:
        daily = period_df.groupby(period_df["date"].apply(lambda d: d.day))["amount"].sum()
    daily = daily.reindex(range(1, max_x + 1), fill_value=0.0)
    cum = daily.cumsum()
    return pd.DataFrame({"x": cum.index, "cumulative": cum.values})


def render_annotation_editor(
    txn_id: int,
    current: dict,
    api_base: str,
    key_prefix: str = "",
    categories: list[str] | None = None,
) -> None:
    """Render an inline annotation form for a single transaction.

    key_prefix must differ per page to avoid Streamlit widget key collisions:
    use "tx_" on the Transactions page, "cat_" on the Spend page, etc.

    categories: if provided, the category field becomes a searchable selectbox
    with a fallback text input for entering a brand-new category name.
    """
    _raw_cat = current.get("user_category")
    current_cat = _raw_cat if isinstance(_raw_cat, str) else ""

    with st.form(f"{key_prefix}ann_form_{txn_id}"):
        st.caption(f"Transaction #{txn_id}")

        if categories is not None:
            # Coerce to plain Python str — pandas rows return numpy.str_ subclasses
            # which break sorted() when mixed with str in CPython 3.13.
            clean = sorted({str(c) for c in (categories or []) if c is not None and not isinstance(c, float) and c})
            clean_set = frozenset(clean)
            current_cat = str(current_cat) if current_cat else ""
            options = [""] + clean
            if current_cat and current_cat not in clean_set:
                options = [""] + sorted(clean_set | {current_cat})
            try:
                idx = options.index(current_cat)
            except ValueError:
                idx = 0
            selected_cat = st.selectbox(
                "Category override",
                options=options,
                index=idx,
                format_func=lambda x: x or "(inherit from rules/Plaid)",
            )
            new_cat_input = st.text_input(
                "Or type a new category",
                value="",
                placeholder="Leave blank to use selection above",
            )
            # Explicit new entry takes priority over selectbox selection.
            cat_val = new_cat_input.strip() or selected_cat
        else:
            cat_val = st.text_input(
                "Category override",
                value=current_cat,
                placeholder="Leave blank to use rule/Plaid category",
            )

        merchant_val = st.text_input(
            "Merchant name override",
            value=current.get("merchant_name_override") or "",
            placeholder="Leave blank to use Plaid merchant",
        )
        notes_val = st.text_area("Notes", value=current.get("notes") or "")
        reviewed_val = st.checkbox("Reviewed", value=bool(current.get("reviewed", False)))
        refund_options = {
            "Automatic": "auto",
            "Confirmed refund": "confirmed",
            "Not a refund": "not_refund",
        }
        current_refund = current.get("refund_status")
        refund_label = {
            "confirmed": "Confirmed refund",
            "not_refund": "Not a refund",
        }.get(current_refund, "Automatic")
        refund_choice = st.selectbox(
            "Refund classification",
            options=list(refund_options),
            index=list(refund_options).index(refund_label),
            help="Automatic preserves high-confidence matching; manual choices override it.",
        )
        submitted = st.form_submit_button("Save")

    if submitted:
        payload = {
            "user_category": cat_val.strip() or None,
            "merchant_name_override": merchant_val.strip() or None,
            "notes": notes_val.strip() or None,
            "reviewed": reviewed_val,
            "refund_status": refund_options[refund_choice],
        }
        resp = api_patch(f"/transactions/{txn_id}/annotation", json=payload, base=api_base)
        if resp.ok:
            st.success("Saved.")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(f"Save failed ({resp.status_code}): {extract_error_message(resp)}")
