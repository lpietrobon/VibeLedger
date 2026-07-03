from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_lib import (
    DEFAULT_DB,
    add_cashflow_columns,
    apply_filters,
    category_color,
    compact_page,
    is_dark_theme,
    load_transactions,
    render_app_navigation,
    sidebar_filters,
    spend_transactions,
    tech_sidebar,
)

st.set_page_config(page_title="Cashflow Sankey", layout="wide")
compact_page()
render_app_navigation()
st.title("Cashflow Sankey")
st.caption("See how income flows through top-level spending buckets into individual categories.")

try:
    df = load_transactions(st.session_state.get("db_path") or DEFAULT_DB)
except Exception as e:
    st.error(f"Failed to load DB: {e}")
    st.stop()

db_path, start_d, end_d, accounts, excl_xfer = sidebar_filters(df)
tech_sidebar(show_api=False)
f = apply_filters(df, start_d, end_d, accounts, excl_xfer)

if f.empty:
    st.warning("No transactions in this window.")
    st.stop()

cashflow = add_cashflow_columns(f)
income = float(cashflow["income"].sum())
income_rows = cashflow[cashflow["income"] > 0].copy()
income_rows["income_category"] = income_rows["effective_category"].fillna("Uncategorized")
income_totals = (
    income_rows.groupby("income_category")["income"]
    .sum()
    .sort_values(ascending=False)
)
spend = spend_transactions(f)
spend["bucket"] = (
    spend["effective_category"]
    .fillna("Uncategorized")
    .astype(str)
    .str.split("/")
    .str[0]
    .str.strip()
    .replace("", "Uncategorized")
)
spend["category"] = spend["effective_category"].fillna("Uncategorized").astype(str).str.strip()
spend.loc[spend["category"] == "", "category"] = "Uncategorized"
bucket_totals = spend.groupby("bucket")["amount"].sum().sort_values(ascending=False)
bucket_totals = bucket_totals[bucket_totals > 0]
category_totals = (
    spend.groupby(["bucket", "category"], as_index=False)["amount"]
    .sum()
    .sort_values(["bucket", "amount"], ascending=[True, False])
)
category_totals = category_totals[
    category_totals["bucket"].isin(bucket_totals.index) & (category_totals["amount"] > 0)
]
bucket_label, bucket_control = st.columns([1, 5])
with bucket_label:
    st.markdown("**Expand**")
with bucket_control:
    expand_options = ["Income sources", *bucket_totals.index.tolist()]
    selected_bucket = st.pills(
        "Expand a flow",
        options=expand_options,
        selection_mode="single",
        key="sankey_expanded_bucket",
        help=(
            "Tap Income sources to show upstream income categories, or tap a spending "
            "bucket to show its categories. Tap the selected pill again to collapse it."
        ),
        label_visibility="collapsed",
    )
visible_category_totals = (
    category_totals[category_totals["bucket"] == selected_bucket]
    if selected_bucket and selected_bucket != "Income sources"
    else category_totals.iloc[0:0]
)
visible_income_totals = income_totals if selected_bucket == "Income sources" else income_totals.iloc[0:0]
total_spend = float(bucket_totals.sum())
savings = max(income - total_spend, 0.0)
deficit = max(total_spend - income, 0.0)

if income <= 0 and total_spend <= 0:
    st.info("No income or spending is available for this period.")
    st.stop()


def _compact_value(value: float) -> str:
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        return f"{value / 1_000_000:.1f}m$"
    if magnitude >= 1_000:
        return f"{value / 1_000:.1f}k$"
    return f"{value:,.0f}$"


def _node_label(name: str, value: float) -> str:
    return f"{name}<br>{_compact_value(value)}"


labels = [_node_label("Income", income)]
income_idx = 0
income_source_indices: dict[str, int] = {}
for income_category, amount in visible_income_totals.items():
    income_source_indices[income_category] = len(labels)
    labels.append(_node_label(income_category, float(amount)))

deficit_idx = None
if deficit > 0:
    deficit_idx = len(labels)
    labels.append(_node_label("Deficit funding", deficit))

bucket_indices: dict[str, int] = {}
for bucket, amount in bucket_totals.items():
    bucket_indices[bucket] = len(labels)
    labels.append(_node_label(bucket, float(amount)))

category_indices: dict[tuple[str, str], int] = {}
for row in visible_category_totals.itertuples(index=False):
    key = (row.bucket, row.category)
    category_indices[key] = len(labels)
    category_label = row.category.split("/", 1)[1].strip() if "/" in row.category else "Other"
    labels.append(_node_label(category_label or "Other", float(row.amount)))

savings_idx = None
if savings > 0:
    savings_idx = len(labels)
    labels.append(_node_label("Savings / unspent", savings))

sources: list[int] = []
targets: list[int] = []
values: list[float] = []
colors: list[str] = []

for income_category, amount in visible_income_totals.items():
    sources.append(income_source_indices[income_category])
    targets.append(income_idx)
    values.append(float(amount))
    colors.append("rgba(44, 160, 44, 0.35)")

income_available_for_spend = min(income, total_spend)
for bucket, amount in bucket_totals.items():
    amount = float(amount)
    income_share = amount * income_available_for_spend / total_spend if total_spend else 0.0
    deficit_share = amount - income_share
    if income_share > 0:
        sources.append(income_idx)
        targets.append(bucket_indices[bucket])
        values.append(income_share)
        colors.append("rgba(44, 160, 44, 0.45)")
    if deficit_share > 0 and deficit_idx is not None:
        sources.append(deficit_idx)
        targets.append(bucket_indices[bucket])
        values.append(deficit_share)
        colors.append("rgba(214, 39, 40, 0.4)")

for row in visible_category_totals.itertuples(index=False):
    sources.append(bucket_indices[row.bucket])
    targets.append(category_indices[(row.bucket, row.category)])
    values.append(float(row.amount))
    colors.append("rgba(148, 103, 189, 0.35)")

if savings_idx is not None:
    sources.append(income_idx)
    targets.append(savings_idx)
    values.append(savings)
    colors.append("rgba(31, 119, 180, 0.45)")

# Spending buckets (and their expanded children) wear their stable app-wide
# category color, so "Food" is the same hue here as on every other page.
dark = is_dark_theme()
node_colors = ["#2ca02c"]
node_colors.extend(["#8fd18f"] * len(visible_income_totals))
if deficit_idx is not None:
    node_colors.append("#d62728")
node_colors.extend([category_color(bucket, dark) for bucket in bucket_totals.index])
node_colors.extend(
    [category_color(row.bucket, dark) for row in visible_category_totals.itertuples(index=False)]
)
if savings_idx is not None:
    node_colors.append("#1f77b4")

fig = go.Figure(
    go.Sankey(
        arrangement="snap",
        node={
            "label": labels,
            "color": node_colors,
            "pad": 18,
            "thickness": 22,
            "line": {"color": "rgba(80,80,80,0.35)", "width": 0.5},
        },
        link={
            "source": sources,
            "target": targets,
            "value": values,
            "color": colors,
            "hovertemplate": "%{source.label} → %{target.label}<br>$%{value:,.2f}<extra></extra>",
        },
    )
)
fig.update_layout(
    title="Income allocation by bucket and category",
    height=max(520, 70 + 38 * len(labels)),
    margin={"l": 20, "r": 20, "t": 60, "b": 20},
)
st.plotly_chart(fig, use_container_width=True)

if deficit > 0:
    st.caption(
        "Spending exceeded recorded income in this period. The red “Deficit funding” flow represents the difference."
    )
