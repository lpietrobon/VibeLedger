import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_lib import (
    add_cashflow_columns,
    apply_filters,
    compact_page,
    load_transactions,
    render_app_navigation,
    sidebar_filters,
    tech_sidebar,
)

st.set_page_config(page_title="Cashflow", layout="wide")
compact_page()
render_app_navigation()
st.title("Cashflow")

try:
    df = load_transactions(st.session_state.get("db_path", ""))
except Exception:
    from dashboard_lib import DEFAULT_DB
    df = load_transactions(DEFAULT_DB)

db_path, start_d, end_d, accounts, excl_xfer = sidebar_filters(df)
tech_sidebar(show_api=False)
f = apply_filters(df, start_d, end_d, accounts, excl_xfer)

if f.empty:
    st.warning("No transactions in this window.")
    st.stop()

f = add_cashflow_columns(f)
f["month"] = pd.to_datetime(f["date"]).dt.strftime("%Y-%m")

monthly = f.groupby("month", as_index=False).agg(
    expense=("expense", "sum"),
    income=("income", "sum"),
)
monthly["net"] = monthly["income"] - monthly["expense"]

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=monthly["month"],
        y=monthly["income"],
        name="Income",
        mode="lines",
        fill="tozeroy",
        fillcolor="rgba(44, 160, 44, 0.6)",
        line={"color": "#2ca02c", "width": 2},
    )
)
fig.add_trace(
    go.Scatter(
        x=monthly["month"],
        y=-monthly["expense"],
        name="Expenses",
        mode="lines",
        fill="tozeroy",
        fillcolor="rgba(214, 39, 40, 0.6)",
        line={"color": "#d62728", "width": 2},
    )
)
fig.add_trace(
    go.Scatter(
        x=monthly["month"],
        y=monthly["net"],
        name="Net cashflow",
        mode="lines+markers",
        line={"color": "#1f77b4", "width": 4},
    )
)
fig.update_layout(
    title="Monthly cashflow",
    hovermode="x unified",
    legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
    xaxis_title="Month",
    yaxis_title="Cashflow ($)",
    yaxis={"tickprefix": "$", "zeroline": True, "zerolinecolor": "rgba(80, 80, 80, 0.6)"},
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Monthly detail")
show = monthly.copy()
for c in ["income", "expense", "net"]:
    show[c] = show[c].map(lambda v: f"${v:,.2f}")
st.dataframe(show, use_container_width=True, hide_index=True)

if len(monthly) >= 2:
    this_m, prev_m = monthly.iloc[-1], monthly.iloc[-2]
    st.subheader("Latest vs previous month")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Income", f"${this_m['income']:,.2f}", delta=f"{this_m['income']-prev_m['income']:+.2f}")
    with c2:
        st.metric("Expense", f"${this_m['expense']:,.2f}", delta=f"{this_m['expense']-prev_m['expense']:+.2f}", delta_color="inverse")
    with c3:
        st.metric("Net", f"${this_m['net']:,.2f}", delta=f"{this_m['net']-prev_m['net']:+.2f}")
