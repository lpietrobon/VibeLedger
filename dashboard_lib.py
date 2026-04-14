"""Shared helpers for the multipage Streamlit dashboard.

Heavy reads hit SQLite directly (cached via st.cache_data). Mutations go through
the FastAPI server — see api_post/api_delete — so auth middleware and write-path
logic are exercised end-to-end.
"""
from __future__ import annotations

import os
import sqlite3
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


@st.cache_data(ttl=60)
def load_transactions(db_path: str) -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    try:
        q = """
        SELECT t.id, t.account_id, t.date, t.amount, t.name, t.merchant_name,
               t.pending,
               t.plaid_category_primary,
               COALESCE(ta.user_category, t.plaid_category_primary, 'uncategorized') AS effective_category,
               COALESCE(ta.is_transfer_override, 0) AS is_transfer_override,
               a.name AS account_name, a.mask, a.type AS account_type, a.subtype AS account_subtype,
               tp_out.id AS pair_as_out, tp_in.id AS pair_as_in
        FROM transactions t
        LEFT JOIN transaction_annotations ta ON ta.transaction_id=t.id
        LEFT JOIN accounts a ON a.id=t.account_id
        LEFT JOIN transfer_pairs tp_out ON tp_out.txn_out_id=t.id
        LEFT JOIN transfer_pairs tp_in ON tp_in.txn_in_id=t.id
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
            SELECT a.id, a.name, a.mask, a.type, a.subtype,
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

    accounts = sorted(df["account_name"].fillna("Unknown").unique().tolist())
    selected = st.sidebar.multiselect("Accounts", accounts, default=accounts, key="accounts")
    exclude_transfers = st.sidebar.checkbox("Exclude transfers", value=True, key="excl_xfer")
    return db_path, start_d, end_d, selected, exclude_transfers


def apply_filters(df: pd.DataFrame, start_d, end_d, accounts, exclude_transfers: bool) -> pd.DataFrame:
    f = df.copy()
    if start_d is not None:
        f = f[(f["date"] >= start_d) & (f["date"] <= end_d)]
    if accounts:
        f = f[f["account_name"].fillna("Unknown").isin(accounts)]
    if exclude_transfers and "is_transfer" in f.columns:
        f = f[~f["is_transfer"]]
    return f
