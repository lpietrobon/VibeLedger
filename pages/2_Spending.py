from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard_lib import (
    DEFAULT_DB,
    apply_date_filter,
    apply_scope_filters,
    apply_transaction_filter_tokens,
    compact_page,
    cumulative_series,
    load_transactions,
    parse_transaction_filter_query,
    period_bounds_n,
    render_annotation_editor,
    render_app_navigation,
    sidebar_filters,
    spend_transactions,
    spending_period_summary,
    tech_sidebar,
)

st.set_page_config(page_title="Spending", layout="wide")
compact_page()
render_app_navigation()
st.title("Spending")

try:
    df = load_transactions(st.session_state.get("db_path") or DEFAULT_DB)
except Exception as exc:
    st.error(f"Failed to load DB: {exc}")
    st.stop()

db_path, start_d, end_d, accounts, exclude_transfers = sidebar_filters(df)

if df.empty:
    tech_sidebar()
    st.stop()

categories = sorted(df["effective_category"].fillna("Uncategorized").unique().tolist())
selected_categories = st.sidebar.multiselect(
    "Categories",
    categories,
    default=categories,
    key="spend_categories",
)
_, api_base = tech_sidebar()

if "spend_filters" not in st.session_state:
    st.session_state.spend_filters = []
if "spend_search_counter" not in st.session_state:
    st.session_state.spend_search_counter = 0

comparison_base = apply_scope_filters(df, accounts, exclude_transfers)
comparison_base = comparison_base[
    comparison_base["effective_category"].fillna("Uncategorized").isin(selected_categories)
]
selected_window = apply_date_filter(comparison_base, start_d, end_d)
filtered_window = apply_transaction_filter_tokens(selected_window, st.session_state.spend_filters)
comparison_window = apply_transaction_filter_tokens(
    comparison_base,
    st.session_state.spend_filters,
    skip_dates=True,
)

anchor = min(date.today(), end_d) if end_d else date.today()
control_col, context_col = st.columns([2, 5])
with control_col:
    granularity_label = st.segmented_control(
        "Period",
        ["Monthly", "Yearly"],
        default="Monthly",
        label_visibility="collapsed",
        key="spend_granularity",
    )
with context_col:
    st.caption("Compare the current period with recent history; use sidebar filters to change scope.")

granularity = "yearly" if granularity_label == "Yearly" else "monthly"
periods = period_bounds_n(granularity, anchor, n_periods=4)
all_spend = spend_transactions(comparison_window)
period_spends = [
    all_spend[(all_spend["date"] >= period["start"]) & (all_spend["date"] <= period["end"])]
    for period in periods
]

current_period = periods[0]
if granularity == "yearly":
    period_total_days = date(anchor.year, 12, 31).timetuple().tm_yday
else:
    period_total_days = pd.Period(current_period["start"], freq="M").days_in_month

summary = spending_period_summary(
    period_spends[0],
    period_spends[1],
    elapsed_days=current_period["len"],
    total_days=period_total_days,
)
change_text = (
    f"{summary['change_pct']:+.1f}% vs {periods[1]['label']}"
    if summary["change_pct"] is not None
    else f"No {periods[1]['label']} comparison"
)
driver = summary["top_driver"] or {"category": "No spending", "amount": 0.0}

st.markdown(
    f"""
    <style>
    .spend-summary-grid {{
        display:grid;
        grid-template-columns:repeat(4,minmax(0,1fr));
        gap:.7rem;
        margin:.2rem 0 .8rem;
    }}
    .spend-summary-card {{
        border:1px solid rgba(128,128,128,.22);
        border-radius:.7rem;
        padding:.65rem .75rem;
        min-width:0;
    }}
    .spend-summary-label {{font-size:.78rem;opacity:.72}}
    .spend-summary-value {{font-size:1.4rem;font-weight:650;line-height:1.2;overflow:hidden;text-overflow:ellipsis}}
    .spend-summary-note {{font-size:.72rem;opacity:.68;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    @media(max-width:768px) {{
        .spend-summary-grid {{grid-template-columns:repeat(2,minmax(0,1fr));gap:.45rem}}
        .spend-summary-card {{padding:.5rem .6rem}}
        .spend-summary-value {{font-size:1.15rem}}
    }}
    </style>
    <div class="spend-summary-grid">
      <div class="spend-summary-card"><div class="spend-summary-label">{periods[0]['label']} spend</div><div class="spend-summary-value">${summary['total']:,.0f}</div></div>
      <div class="spend-summary-card"><div class="spend-summary-label">Period change</div><div class="spend-summary-value">${summary['change']:+,.0f}</div><div class="spend-summary-note">{change_text}</div></div>
      <div class="spend-summary-card"><div class="spend-summary-label">Projected pace</div><div class="spend-summary-value">${summary['projection']:,.0f}</div><div class="spend-summary-note">At the current daily pace</div></div>
      <div class="spend-summary-card"><div class="spend-summary-label">Top driver</div><div class="spend-summary-value">{driver['category']}</div><div class="spend-summary-note">${driver['amount']:,.0f}</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

cumulative_frames = []
for period, period_spend in zip(periods, period_spends):
    cumulative = cumulative_series(period_spend, granularity, period["len"])
    cumulative["series"] = period["label"]
    cumulative_frames.append(cumulative)

combined = pd.concat(cumulative_frames, ignore_index=True)
labels = [period["label"] for period in periods]
primary_chart = px.line(
    combined,
    x="x",
    y="cumulative",
    color="series",
    line_dash="series",
    line_dash_map={labels[0]: "solid", **{label: "dot" for label in labels[1:]}},
    category_orders={"series": labels},
    title="Cumulative spending pace",
)
primary_chart.update_layout(
    xaxis_title="Day of month" if granularity == "monthly" else "Day of year",
    yaxis_title="Spend ($)",
    legend_title=None,
    hovermode="x unified",
    margin={"l": 10, "r": 10, "t": 50, "b": 10},
)
st.plotly_chart(primary_chart, width="stretch")

drivers_tab, trends_tab = st.tabs(["Drivers", "Advanced trends"])

with drivers_tab:
    current_label, previous_label = periods[0]["label"], periods[1]["label"]
    comparison = pd.concat(
        [
            period_spends[0].assign(period=current_label),
            period_spends[1].assign(period=previous_label),
        ],
        ignore_index=True,
    )
    if comparison.empty:
        st.caption("No category comparison is available.")
    else:
        comparison["category"] = (
            comparison["effective_category"]
            .fillna("Uncategorized")
            .astype(str)
            .str.split("/")
            .str[0]
            .str.strip()
            .replace("", "Uncategorized")
        )
        category_comparison = (
            comparison.groupby(["category", "period"], as_index=False)["amount"].sum()
        )
        order = (
            category_comparison.groupby("category")["amount"]
            .sum()
            .nlargest(10)
            .sort_values()
            .index.tolist()
        )
        category_comparison = category_comparison[
            category_comparison["category"].isin(order)
        ]
        driver_chart = px.bar(
            category_comparison,
            x="amount",
            y="category",
            color="period",
            barmode="group",
            orientation="h",
            category_orders={
                "category": order,
                "period": [current_label, previous_label],
            },
            title=f"{current_label} vs {previous_label}",
        )
        driver_chart.update_layout(
            xaxis_title="Spend",
            yaxis_title=None,
            legend_title=None,
            margin={"l": 10, "r": 10, "t": 50, "b": 10},
        )
        st.plotly_chart(driver_chart, width="stretch")

with trends_tab:
    option_col, count_col = st.columns(2)
    with option_col:
        trend_dimension = st.segmented_control(
            "Break down by",
            ["Category", "Merchant"],
            default="Category",
            key="spend_trend_dimension",
        )
    with count_col:
        trend_top_n = st.slider("Top series", 3, 10, 5, key="spend_trend_top_n")

    trend_source = spend_transactions(filtered_window).copy()
    trend_source["month"] = pd.to_datetime(trend_source["date"]).dt.to_period("M").astype(str)
    if trend_dimension == "Merchant":
        trend_source["series"] = trend_source["effective_merchant"].fillna("Unknown")
    else:
        trend_source["series"] = (
            trend_source["effective_category"]
            .fillna("Uncategorized")
            .astype(str)
            .str.split("/")
            .str[0]
            .str.strip()
            .replace("", "Uncategorized")
        )

    if trend_source.empty:
        st.caption("No spending data in the selected window.")
    else:
        top_series = trend_source.groupby("series")["amount"].sum().nlargest(trend_top_n).index
        trend = (
            trend_source[trend_source["series"].isin(top_series)]
            .groupby(["month", "series"], as_index=False)["amount"]
            .sum()
        )
        trend_chart = px.line(
            trend,
            x="month",
            y="amount",
            color="series",
            markers=True,
            title=f"Monthly spending by {trend_dimension.lower()}",
        )
        trend_chart.update_layout(
            xaxis_title="Month",
            yaxis_title="Spend ($)",
            legend_title=None,
            hovermode="x unified",
            margin={"l": 10, "r": 10, "t": 50, "b": 10},
        )
        st.plotly_chart(trend_chart, width="stretch")

with st.expander("Transaction samples and annotation", expanded=False):
    def on_spend_search_submit() -> None:
        key = f"spend_search_{st.session_state.spend_search_counter}"
        raw = st.session_state.get(key, "").strip()
        if raw:
            st.session_state.spend_filters.extend(parse_transaction_filter_query(raw))
            st.session_state.spend_search_counter += 1

    st.text_input(
        "Search transaction samples",
        label_visibility="collapsed",
        placeholder="Merchant or filters: cat:Food  >500  from:2026-05",
        key=f"spend_search_{st.session_state.spend_search_counter}",
        on_change=on_spend_search_submit,
    )

    active_filters = st.session_state.spend_filters
    if active_filters:
        labels_active = [item["label"] for item in active_filters]
        remaining = st.pills(
            "Active filters",
            options=labels_active,
            selection_mode="multi",
            default=labels_active,
            label_visibility="collapsed",
            key="spend_filter_pills",
        )
        remaining_set = set(remaining or [])
        if remaining_set != set(labels_active):
            st.session_state.spend_filters = [
                item for item in active_filters if item["label"] in remaining_set
            ]
            st.rerun()

    samples_source = apply_transaction_filter_tokens(
        selected_window,
        st.session_state.spend_filters,
    )
    if samples_source.empty:
        st.caption("No transactions match the current filters.")
    else:
        sample_category = st.selectbox(
            "Category",
            sorted(samples_source["effective_category"].fillna("Uncategorized").unique().tolist()),
            key="spend_sample_category",
        )
        samples = (
            samples_source[
                samples_source["effective_category"].fillna("Uncategorized") == sample_category
            ]
            .sort_values("date", ascending=False)
            .head(100)
            .reset_index(drop=True)
        )
        available = [
            column
            for column in [
                "date",
                "amount",
                "effective_merchant",
                "effective_account_name",
                "effective_category",
            ]
            if column in samples.columns
        ]
        event = st.dataframe(
            samples[available],
            width="stretch",
            height=360,
            hide_index=True,
            key="spend_samples_table",
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "date": st.column_config.DateColumn("Date", width="small"),
                "amount": st.column_config.NumberColumn("Amount", width="small", format="$%.2f"),
                "effective_merchant": st.column_config.TextColumn("Merchant"),
                "effective_account_name": st.column_config.TextColumn("Account"),
                "effective_category": st.column_config.TextColumn("Category"),
            },
        )
        selected_rows = (event.selection or {}).get("rows", [])
        if selected_rows:
            row = samples.iloc[selected_rows[0]]
            st.subheader(str(row.get("effective_merchant") or row.get("name") or "Transaction"))
            render_annotation_editor(
                int(row["id"]),
                {
                    "user_category": row.get("user_category"),
                    "merchant_name_override": row.get("merchant_name_override"),
                    "notes": row.get("notes"),
                    "reviewed": row.get("reviewed", False),
                    "refund_status": row.get("refund_status"),
                },
                api_base,
                key_prefix="spend_",
                categories=categories,
            )
