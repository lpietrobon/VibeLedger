"""Shared helpers for the multipage Streamlit dashboard.

Heavy reads hit SQLite directly (cached via st.cache_data). Mutations go through
the FastAPI server — see api_post/api_delete — so auth middleware and write-path
logic are exercised end-to-end.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import streamlit as st


DEFAULT_DB = os.environ.get("VIBELEDGER_DB", str(Path.home() / ".vibeledger" / "vibeledger.db"))
DEFAULT_API = os.environ.get("VIBELEDGER_API", "http://127.0.0.1:8000")
ENV_FILE = Path(__file__).resolve().parent / ".env"


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


def sidebar_filters(df: pd.DataFrame):
    """Shared sidebar: DB path, date range, account multiselect, transfer toggle."""
    from datetime import date, timedelta

    st.sidebar.header("Filters")
    db_path = st.sidebar.text_input("DB path", DEFAULT_DB, key="db_path")

    if df.empty:
        return db_path, None, None, [], True

    min_d, max_d = df["date"].min(), df["date"].max()
    def_start = max(min_d, date.today() - timedelta(days=90))
    start_d, end_d = st.sidebar.date_input(
        "Date range",
        (def_start, max_d),
        min_value=min_d,
        max_value=max_d,
        key="date_range",
    )

    acct_col = "effective_account_name" if "effective_account_name" in df.columns else "account_name"
    accounts = sorted(df[acct_col].fillna("Unknown").unique().tolist())
    selected = st.sidebar.multiselect("Accounts", accounts, default=accounts, key="accounts")
    exclude_transfers = st.sidebar.checkbox("Exclude transfers", value=True, key="excl_xfer")
    return db_path, start_d, end_d, selected, exclude_transfers


def apply_filters(df: pd.DataFrame, start_d, end_d, accounts, exclude_transfers: bool) -> pd.DataFrame:
    f = df.copy()
    if start_d is not None:
        f = f[(f["date"] >= start_d) & (f["date"] <= end_d)]
    if accounts:
        acct_col = "effective_account_name" if "effective_account_name" in f.columns else "account_name"
        f = f[f[acct_col].fillna("Unknown").isin(accounts)]
    if exclude_transfers and "is_transfer" in f.columns:
        f = f[~f["is_transfer"]]
    return f


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
        submitted = st.form_submit_button("Save")

    if submitted:
        payload = {
            "user_category": cat_val.strip() or None,
            "merchant_name_override": merchant_val.strip() or None,
            "notes": notes_val.strip() or None,
            "reviewed": reviewed_val,
        }
        resp = api_patch(f"/transactions/{txn_id}/annotation", json=payload, base=api_base)
        if resp.ok:
            st.success("Saved.")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(f"Save failed ({resp.status_code}): {extract_error_message(resp)}")
