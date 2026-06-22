from __future__ import annotations

import calendar
import re
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard_lib import (
    DEFAULT_DB,
    apply_date_filter,
    apply_scope_filters,
    compact_page,
    cumulative_series,
    load_transactions,
    period_bounds_n,
    render_annotation_editor,
    sidebar_filters,
    spend_transactions,
    tech_sidebar,
)

st.set_page_config(page_title="Spend", layout="wide")
compact_page()
st.title("Spend")

try:
    df = load_transactions(st.session_state.get("db_path") or DEFAULT_DB)
except Exception as e:
    st.error(f"Failed to load DB: {e}")
    st.stop()

db_path, start_d, end_d, accounts, excl_xfer = sidebar_filters(df)

if df.empty:
    tech_sidebar()
    st.stop()

cats = sorted(df["effective_category"].fillna("uncategorized").unique().tolist())
selected_cats = st.sidebar.multiselect("Categories", cats, default=cats, key="cats")

_, api_base = tech_sidebar()

# ── Omnibar ────────────────────────────────────────────────────────────────────
_HINT = "e.g.  whole foods  ·  >500  ·  from:2026-05  ·  to:2026-05-31  ·  account:checking"

if "cat_filters" not in st.session_state:
    st.session_state.cat_filters = []


def _cat_parse_and_add(raw: str) -> None:
    tokens = raw.strip().split()
    text_parts: list[str] = []
    for token in tokens:
        if m := re.match(r"^(?:cat|category):(.+)$", token, re.I):
            st.session_state.cat_filters.append(
                {"type": "category", "value": m.group(1), "label": f"cat: {m.group(1)}"}
            )
        elif m := re.match(r"^(?:amount:)?[>≥](\d+(?:\.\d+)?)$", token):
            v = float(m.group(1))
            st.session_state.cat_filters.append({"type": "amount_min", "value": v, "label": f"≥ ${v:,.0f}"})
        elif m := re.match(r"^(?:amount:)?[<≤](\d+(?:\.\d+)?)$", token):
            v = float(m.group(1))
            st.session_state.cat_filters.append({"type": "amount_max", "value": v, "label": f"≤ ${v:,.0f}"})
        elif m := re.match(r"^from:(\d{4}-\d{2}(?:-\d{2})?)$", token, re.I):
            st.session_state.cat_filters.append({"type": "date_from", "value": m.group(1), "label": f"from {m.group(1)}"})
        elif m := re.match(r"^to:(\d{4}-\d{2}(?:-\d{2})?)$", token, re.I):
            st.session_state.cat_filters.append({"type": "date_to", "value": m.group(1), "label": f"to {m.group(1)}"})
        elif m := re.match(r"^account:(.+)$", token, re.I):
            st.session_state.cat_filters.append({"type": "account", "value": m.group(1), "label": f"account: {m.group(1)}"})
        else:
            text_parts.append(token)
    if text_parts:
        text_val = " ".join(text_parts)
        st.session_state.cat_filters.append({"type": "text", "value": text_val, "label": f'"{text_val}"'})


def _cat_apply_omnibar(base_df: pd.DataFrame, skip_dates: bool = False) -> pd.DataFrame:
    f = base_df.copy()
    for filt in st.session_state.cat_filters:
        ft, fv = filt["type"], filt["value"]
        if skip_dates and ft in ("date_from", "date_to"):
            continue
        if ft == "text":
            term = fv.lower()
            f = f[
                f["name"].fillna("").str.lower().str.contains(term, regex=False)
                | f["effective_merchant"].fillna("").str.lower().str.contains(term, regex=False)
            ]
        elif ft == "amount_min":
            f = f[f["amount"] >= fv]
        elif ft == "amount_max":
            f = f[f["amount"] <= fv]
        elif ft == "category":
            prefix = fv.lower() + "/"
            f = f[
                (f["effective_category"].fillna("").str.lower() == fv.lower())
                | f["effective_category"].fillna("").str.lower().str.startswith(prefix)
            ]
        elif ft == "date_from":
            parts = list(map(int, fv.split("-")))
            boundary = date(*parts) if len(parts) == 3 else date(parts[0], parts[1], 1)
            f = f[f["date"] >= boundary]
        elif ft == "date_to":
            parts = list(map(int, fv.split("-")))
            boundary = date(*parts) if len(parts) == 3 else date(parts[0], parts[1], calendar.monthrange(parts[0], parts[1])[1])
            f = f[f["date"] <= boundary]
        elif ft == "account":
            f = f[f["account_name"].fillna("").str.lower().str.contains(fv.lower(), regex=False)]
    return f


if "cat_omnibar_counter" not in st.session_state:
    st.session_state.cat_omnibar_counter = 0


def _on_cat_omnibar_change():
    raw = st.session_state.get(f"cat_omnibar_{st.session_state.cat_omnibar_counter}", "").strip()
    if raw:
        _cat_parse_and_add(raw)
        st.session_state.cat_omnibar_counter += 1


_today = min(date.today(), end_d) if end_d else date.today()

# ── Apply filters ──────────────────────────────────────────────────────────────
comparison_base = apply_scope_filters(df, accounts, excl_xfer)
comparison_base = comparison_base[
    comparison_base["effective_category"].fillna("uncategorized").isin(selected_cats)
]
f_base = apply_date_filter(comparison_base, start_d, end_d)
f = _cat_apply_omnibar(f_base)
f_period = _cat_apply_omnibar(comparison_base, skip_dates=True)
spend_period = spend_transactions(f_period)

# ── Spending trends ──────────────────────────────────────────────────────────
granularity = st.radio(
    "Granularity",
    ["Monthly", "Yearly"],
    horizontal=True,
    key="cat_granularity",
    label_visibility="collapsed",
)
gran = "monthly" if granularity == "Monthly" else "yearly"

periods = period_bounds_n(gran, _today, n_periods=4)

period_spends = []
for p in periods:
    p_spend = spend_period[(spend_period["date"] >= p["start"]) & (spend_period["date"] <= p["end"])]
    period_spends.append(p_spend)

cum_frames = []
for p, p_spend in zip(periods, period_spends):
    cum = cumulative_series(p_spend, gran, p["len"])
    cum["series"] = p["label"]
    cum_frames.append(cum)

combined = pd.concat(cum_frames, ignore_index=True)
labels = [p["label"] for p in periods]
x_title = "Day of month" if gran == "monthly" else "Day of year"
fig3 = px.line(
    combined, x="x", y="cumulative", color="series",
    line_dash="series",
    line_dash_map={labels[0]: "solid", **{lbl: "dot" for lbl in labels[1:]}},
    category_orders={"series": labels},
    title="Cumulative spend",
)
fig3.update_layout(xaxis_title=x_title, yaxis_title="Cumulative spend ($)", legend_title=None)
st.plotly_chart(fig3, use_container_width=True)

cur_spend, prev_spend = period_spends[0], period_spends[1]
cur_label, prev_label = periods[0]["label"], periods[1]["label"]
m = pd.concat([cur_spend.assign(bucket=cur_label), prev_spend.assign(bucket=prev_label)], ignore_index=True)
if not m.empty:
    cmp = m.groupby(["effective_category", "bucket"], as_index=False)["amount"].sum()
    # Order categories by combined spend so the biggest are at the top
    order = (
        cmp.groupby("effective_category", as_index=False)["amount"].sum()
        .sort_values("amount", ascending=True)
        .tail(12)["effective_category"]
        .tolist()
    )
    cmp = cmp[cmp["effective_category"].isin(order)]
    fig2 = px.bar(
        cmp, x="amount", y="effective_category", color="bucket",
        barmode="group", orientation="h",
        category_orders={"effective_category": order, "bucket": [cur_label, prev_label]},
        title=f"{cur_label} vs {prev_label} by category",
    )
    fig2.update_layout(yaxis_title=None, xaxis_title="Spend", legend_title=None)
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.caption("No data for the current or previous period in the filtered range.")

# ── Category and merchant trends ─────────────────────────────────────────────
st.subheader("Category and merchant trends")
dimension_label, dimension_control = st.columns([1, 5])
with dimension_label:
    st.markdown("**Breakdown**")
with dimension_control:
    trend_dimension = st.radio(
        "Break down by",
        ["Category", "Merchant"],
        horizontal=True,
        key="spend_trend_dimension",
        label_visibility="collapsed",
    )
trend_top_n = st.slider("Top series", 3, 12, 6, key="spend_trend_top_n")

trend_source = spend_transactions(f)
trend_source["month"] = pd.to_datetime(trend_source["date"]).dt.to_period("M").astype(str)
if trend_dimension == "Category":
    trend_source["series"] = (
        trend_source["effective_category"]
        .fillna("Uncategorized")
        .astype(str)
        .str.split("/")
        .str[0]
        .str.strip()
        .replace("", "Uncategorized")
    )
else:
    trend_source["series"] = trend_source["effective_merchant"].fillna("Unknown")

if trend_source.empty:
    st.caption("No spending data in the filtered range.")
else:
    top_series = (
        trend_source.groupby("series")["amount"]
        .sum()
        .abs()
        .nlargest(trend_top_n)
        .index
    )
    trend = (
        trend_source[trend_source["series"].isin(top_series)]
        .groupby(["month", "series"], as_index=False)["amount"]
        .sum()
    )
    month_series_grid = pd.MultiIndex.from_product(
        [sorted(trend["month"].unique()), top_series],
        names=["month", "series"],
    )
    trend = (
        trend.set_index(["month", "series"])
        .reindex(month_series_grid, fill_value=0)
        .reset_index()
    )
    fig_trend = px.area(
        trend,
        x="month",
        y="amount",
        color="series",
        title=f"Monthly spend by {'category bucket' if trend_dimension == 'Category' else 'merchant'}",
    )
    fig_trend.update_layout(
        xaxis_title="Month",
        yaxis_title="Spend ($)",
        legend_title=None,
        hovermode="x unified",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ── Transaction samples ───────────────────────────────────────────────────────
st.subheader("Transaction samples")

st.text_input(
    "Filter",
    label_visibility="collapsed",
    placeholder=_HINT,
    key=f"cat_omnibar_{st.session_state.cat_omnibar_counter}",
    on_change=_on_cat_omnibar_change,
)

active = st.session_state.cat_filters
if active:
    labels_active = [flt["label"] for flt in active]
    pills_col, clear_col = st.columns([11, 1])
    with pills_col:
        remaining = st.pills(
            "Active filters",
            options=labels_active,
            selection_mode="multi",
            default=labels_active,
            label_visibility="collapsed",
            key="cat_pills",
        )
    with clear_col:
        if st.button("✕ all", key="cat_chip_clear", use_container_width=True):
            st.session_state.cat_filters.clear()
            st.rerun()

    remaining_set = set(remaining or [])
    if remaining_set != set(labels_active):
        st.session_state.cat_filters = [flt for flt in active if flt["label"] in remaining_set]
        st.rerun()

if not f.empty:
    cat_pick = st.selectbox("Pick a category", sorted(f["effective_category"].fillna("uncategorized").unique().tolist()))
    samples = f[f["effective_category"].fillna("uncategorized") == cat_pick].sort_values("date", ascending=False).head(200)

    display_cols = ["date", "amount", "effective_account_name", "effective_merchant", "name", "effective_category"]
    available = [c for c in display_cols if c in samples.columns]
    event = st.dataframe(
        samples[available].reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
        key="cat_samples_table",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "date": st.column_config.DateColumn("date", width="small"),
            "amount": st.column_config.NumberColumn("amount", width="small", format="$%.2f"),
            "effective_account_name": st.column_config.TextColumn("account", width="medium"),
            "effective_merchant": st.column_config.TextColumn("merchant", width="medium"),
            "name": st.column_config.TextColumn("name", width=None),
            "effective_category": st.column_config.TextColumn("category", width="medium"),
        },
    )
    st.caption("Click a row to annotate it.")

    selected_rows = (event.selection or {}).get("rows", [])
    if selected_rows:
        row_idx = selected_rows[0]
        sel_row = samples.iloc[row_idx]
        txn_id = int(sel_row["id"])
        st.divider()
        merchant_display = sel_row.get("effective_merchant") or sel_row.get("name", "")
        st.subheader(f"Annotate: {merchant_display}  ·  {sel_row['date']}  ·  ${float(sel_row['amount']):,.2f}")
        current = {
            "user_category": sel_row.get("user_category"),
            "merchant_name_override": sel_row.get("merchant_name_override"),
            "notes": sel_row.get("notes"),
            "reviewed": sel_row.get("reviewed", False),
            "refund_status": sel_row.get("refund_status"),
        }
        all_cats = sorted({c for c in f_base["effective_category"].fillna("uncategorized").unique().tolist() if type(c) is str})
        render_annotation_editor(txn_id, current, api_base, key_prefix="cat_", categories=all_cats)
