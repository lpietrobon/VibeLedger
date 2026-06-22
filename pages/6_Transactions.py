from __future__ import annotations

import calendar
import re
from datetime import date as dt

import streamlit as st

from dashboard_lib import (
    DEFAULT_DB,
    apply_filters,
    compact_page,
    load_transactions,
    render_app_navigation,
    render_annotation_editor,
    sidebar_filters,
    tech_sidebar,
)

st.set_page_config(page_title="Transactions – VibeLedger", layout="wide")
compact_page()
render_app_navigation()
st.title("Transactions")

try:
    df = load_transactions(DEFAULT_DB)
except Exception as e:
    st.error(f"Could not load transactions: {e}")
    st.stop()

# Sidebar: shared coarse scope (date range, accounts, transfer toggle)
db_path, start_d, end_d, accounts, excl_xfer = sidebar_filters(df)
_, api_base = tech_sidebar()

# Apply shared filters → base frame the omnibar further narrows
f_base = apply_filters(df, start_d, end_d, accounts, excl_xfer)

# ── Omnibar state ─────────────────────────────────────────────────────────────
if "tx_filters" not in st.session_state:
    st.session_state.tx_filters = []

_HINT = (
    "e.g.  radio gatsby  ·  cat:Food  ·  >500  ·  <50  ·  "
    "from:2026-03  ·  to:2026-05  ·  account:checking  ·  uncat"
)


def _parse_and_add(raw: str) -> None:
    tokens = raw.strip().split()
    text_parts: list[str] = []
    for token in tokens:
        if m := re.match(r"^(?:cat|category):(.+)$", token, re.I):
            st.session_state.tx_filters.append(
                {"type": "category", "value": m.group(1), "label": f"cat: {m.group(1)}"}
            )
        elif m := re.match(r"^(?:amount:)?[>≥](\d+(?:\.\d+)?)$", token):
            v = float(m.group(1))
            st.session_state.tx_filters.append(
                {"type": "amount_min", "value": v, "label": f"≥ ${v:,.0f}"}
            )
        elif m := re.match(r"^(?:amount:)?[<≤](\d+(?:\.\d+)?)$", token):
            v = float(m.group(1))
            st.session_state.tx_filters.append(
                {"type": "amount_max", "value": v, "label": f"≤ ${v:,.0f}"}
            )
        elif m := re.match(r"^from:(\d{4}-\d{2}(?:-\d{2})?)$", token, re.I):
            st.session_state.tx_filters.append(
                {"type": "date_from", "value": m.group(1), "label": f"from {m.group(1)}"}
            )
        elif m := re.match(r"^to:(\d{4}-\d{2}(?:-\d{2})?)$", token, re.I):
            st.session_state.tx_filters.append(
                {"type": "date_to", "value": m.group(1), "label": f"to {m.group(1)}"}
            )
        elif m := re.match(r"^account:(.+)$", token, re.I):
            st.session_state.tx_filters.append(
                {"type": "account", "value": m.group(1), "label": f"account: {m.group(1)}"}
            )
        elif re.match(r"^uncat(?:egorized)?$", token, re.I):
            st.session_state.tx_filters.append(
                {"type": "uncategorized", "value": True, "label": "uncategorized only"}
            )
        else:
            text_parts.append(token)
    if text_parts:
        text_val = " ".join(text_parts)
        st.session_state.tx_filters.append(
            {"type": "text", "value": text_val, "label": f'"{text_val}"'}
        )


def _apply_omnibar(base_df):
    f = base_df.copy()
    for filt in st.session_state.tx_filters:
        ft, fv = filt["type"], filt["value"]
        if ft == "text":
            term = fv.lower()
            f = f[
                f["name"].fillna("").str.lower().str.contains(term, regex=False)
                | f["effective_merchant"].fillna("").str.lower().str.contains(term, regex=False)
            ]
        elif ft == "category":
            prefix = fv.lower() + "/"
            f = f[
                (f["effective_category"].fillna("").str.lower() == fv.lower())
                | f["effective_category"].fillna("").str.lower().str.startswith(prefix)
            ]
        elif ft == "amount_min":
            f = f[f["amount"] >= fv]
        elif ft == "amount_max":
            f = f[f["amount"] <= fv]
        elif ft == "date_from":
            parts = list(map(int, fv.split("-")))
            boundary = dt(*parts) if len(parts) == 3 else dt(parts[0], parts[1], 1)
            f = f[f["date"] >= boundary]
        elif ft == "date_to":
            parts = list(map(int, fv.split("-")))
            boundary = dt(*parts) if len(parts) == 3 else dt(parts[0], parts[1], calendar.monthrange(parts[0], parts[1])[1])
            f = f[f["date"] <= boundary]
        elif ft == "account":
            f = f[f["account_name"].fillna("").str.lower().str.contains(fv.lower(), regex=False)]
        elif ft == "uncategorized":
            f = f[f["effective_category"].fillna("uncategorized") == "uncategorized"]
    return f


# ── Omnibar UI ────────────────────────────────────────────────────────────────
if "omnibar_counter" not in st.session_state:
    st.session_state.omnibar_counter = 0


def _on_omnibar_change():
    raw = st.session_state.get(f"omnibar_{st.session_state.omnibar_counter}", "").strip()
    if raw:
        _parse_and_add(raw)
        st.session_state.omnibar_counter += 1


st.text_input(
    "Search",
    label_visibility="collapsed",
    placeholder=_HINT,
    key=f"omnibar_{st.session_state.omnibar_counter}",
    on_change=_on_omnibar_change,
)

# Active filter chips — st.pills renders as native chip elements.
# Deselecting a chip (clicking it) removes that filter.
active = st.session_state.tx_filters
if active:
    labels = [f["label"] for f in active]
    pills_col, clear_col = st.columns([11, 1])
    with pills_col:
        remaining = st.pills(
            "Active filters",
            options=labels,
            selection_mode="multi",
            default=labels,
            label_visibility="collapsed",
        )
    with clear_col:
        if st.button("✕ all", key="chip_clear", use_container_width=True):
            st.session_state.tx_filters.clear()
            st.rerun()

    remaining_set = set(remaining or [])
    if remaining_set != set(labels):
        st.session_state.tx_filters = [f for f in active if f["label"] in remaining_set]
        st.rerun()

# ── Apply omnibar filters and show table ─────────────────────────────────────
f = _apply_omnibar(f_base)
st.caption(f"{len(f):,} transactions  —  click a row to annotate")

display_cols = ["date", "amount", "effective_merchant", "name", "effective_account_name", "effective_category", "category_source"]
available = [c for c in display_cols if c in f.columns]

event = st.dataframe(
    f[available].reset_index(drop=True),
    use_container_width=True,
    hide_index=True,
    key="tx_table",
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "date": st.column_config.DateColumn("date", width="small"),
        "amount": st.column_config.NumberColumn("amount", width="small", format="$%.2f"),
        "effective_merchant": st.column_config.TextColumn("merchant", width="medium"),
        "name": st.column_config.TextColumn("name", width=None),
        "effective_account_name": st.column_config.TextColumn("account", width="medium"),
        "effective_category": st.column_config.TextColumn("category", width="medium"),
        "category_source": st.column_config.TextColumn("source", width="small"),
    },
)

# ── Annotation panel ──────────────────────────────────────────────────────────
selected_rows = (event.selection or {}).get("rows", [])
if selected_rows:
    row = f.iloc[selected_rows[0]]
    txn_id = int(row["id"])
    st.divider()
    merchant_display = row.get("effective_merchant") or row.get("name", "")
    st.subheader(f"Annotate: {merchant_display}  ·  {row['date']}  ·  ${float(row['amount']):,.2f}")
    current = {
        "user_category": row.get("user_category"),
        "merchant_name_override": row.get("merchant_name_override"),
        "notes": row.get("notes"),
        "reviewed": row.get("reviewed", False),
        "refund_status": row.get("refund_status"),
    }
    all_cats = sorted({c for c in df["effective_category"].fillna("uncategorized").unique().tolist() if type(c) is str})
    render_annotation_editor(txn_id, current, api_base, key_prefix="tx_", categories=all_cats)
else:
    st.info("Click a row to annotate it.")
