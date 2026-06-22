from __future__ import annotations

import calendar
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_lib import (
    DEFAULT_DB,
    apply_date_filter,
    apply_scope_filters,
    compact_page,
    load_transactions,
    render_app_navigation,
    sidebar_filters,
    spend_transactions,
    tech_sidebar,
)

st.set_page_config(page_title="Experimental", layout="wide")
compact_page()
render_app_navigation()
st.title("Experimental")
st.caption("Early-stage views for finding changes and spending patterns.")

try:
    df = load_transactions(st.session_state.get("db_path") or DEFAULT_DB)
except Exception as e:
    st.error(f"Failed to load DB: {e}")
    st.stop()

db_path, start_d, end_d, accounts, excl_xfer = sidebar_filters(df)
tech_sidebar(show_api=False)
comparison_df = apply_scope_filters(df, accounts, excl_xfer)
f = apply_date_filter(comparison_df, start_d, end_d)
spend = spend_transactions(f)
comparison_spend = spend_transactions(comparison_df)

if comparison_spend.empty:
    st.warning("No spending transactions in this window.")
    st.stop()

spend["date"] = pd.to_datetime(spend["date"])
spend["month"] = spend["date"].dt.to_period("M")
spend["category"] = spend["effective_category"].fillna("Uncategorized")
comparison_spend["date"] = pd.to_datetime(comparison_spend["date"])
comparison_spend["month"] = comparison_spend["date"].dt.to_period("M")
comparison_spend["category"] = comparison_spend["effective_category"].fillna("Uncategorized")

st.subheader("Month-over-month movers")
anchor_month = pd.Period(end_d, freq="M") if end_d else comparison_spend["month"].max()
previous_month = anchor_month - 1
comparison = comparison_spend[
    comparison_spend["month"].isin([previous_month, anchor_month])
]
if comparison.empty:
    st.caption("At least two months of spending are needed.")
else:
    totals = comparison.pivot_table(
        index="category",
        columns="month",
        values="amount",
        aggfunc="sum",
        fill_value=0,
    )
    for month in [previous_month, anchor_month]:
        if month not in totals.columns:
            totals[month] = 0.0
    totals["change"] = totals[anchor_month] - totals[previous_month]
    movers = totals.reindex(totals["change"].abs().sort_values(ascending=False).head(12).index)
    movers = movers.sort_values("change")

    colors = ["#d62728" if value > 0 else "#2ca02c" for value in movers["change"]]
    fig_movers = go.Figure(
        go.Bar(
            x=movers["change"],
            y=movers.index,
            orientation="h",
            marker_color=colors,
            customdata=list(zip(movers[previous_month], movers[anchor_month])),
            hovertemplate=(
                "%{y}<br>Change: $%{x:+,.2f}"
                f"<br>{previous_month}: $%{{customdata[0]:,.2f}}"
                f"<br>{anchor_month}: $%{{customdata[1]:,.2f}}<extra></extra>"
            ),
        )
    )
    fig_movers.update_layout(
        title=f"{anchor_month} versus {previous_month}",
        xaxis_title="Change in spend ($)",
        yaxis_title=None,
        height=max(420, 32 * len(movers) + 130),
    )
    st.plotly_chart(fig_movers, use_container_width=True)
    st.caption("Red means spending increased; green means it decreased.")

st.divider()
st.subheader("Calendar heatmap")

heatmap_source = spend if not spend.empty else comparison_spend
years = sorted(heatmap_source["date"].dt.year.unique(), reverse=True)
year_label, year_control = st.columns([1, 5])
with year_label:
    st.markdown("**Year**")
with year_control:
    selected_year = st.selectbox(
        "Year",
        years,
        key="heatmap_year",
        label_visibility="collapsed",
    )
year_spend = (
    heatmap_source[heatmap_source["date"].dt.year == selected_year]
    .groupby(heatmap_source.loc[heatmap_source["date"].dt.year == selected_year, "date"].dt.date)["amount"]
    .sum()
)

first_day = date(selected_year, 1, 1)
last_day = date(selected_year, 12, 31)
all_dates = pd.date_range(first_day, last_day, freq="D")
week_zero = all_dates[0] - pd.Timedelta(days=all_dates[0].weekday())
week_count = int(((all_dates[-1] - week_zero).days // 7) + 1)

z = [[None for _ in range(week_count)] for _ in range(7)]
hover = [["" for _ in range(week_count)] for _ in range(7)]
for ts in all_dates:
    day = ts.date()
    weekday = ts.weekday()
    week = int((ts - week_zero).days // 7)
    amount = float(year_spend.get(day, 0.0))
    z[weekday][week] = amount
    hover[weekday][week] = f"{day:%b %d, %Y}<br>${amount:,.2f}"

month_ticks = []
month_labels = []
for month in range(1, 13):
    month_start = pd.Timestamp(selected_year, month, 1)
    month_ticks.append(int((month_start - week_zero).days // 7))
    month_labels.append(calendar.month_abbr[month])

fig_heatmap = go.Figure(
    go.Heatmap(
        z=z,
        x=list(range(week_count)),
        y=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        text=hover,
        hovertemplate="%{text}<extra></extra>",
        colorscale="YlOrRd",
        colorbar={"title": "Spend"},
        xgap=2,
        ygap=2,
    )
)
fig_heatmap.update_layout(
    title=f"Daily spending intensity · {selected_year}",
    xaxis={"tickmode": "array", "tickvals": month_ticks, "ticktext": month_labels, "side": "top"},
    yaxis={"autorange": "reversed"},
    height=330,
    margin={"l": 45, "r": 30, "t": 80, "b": 20},
)
st.plotly_chart(fig_heatmap, use_container_width=True)
