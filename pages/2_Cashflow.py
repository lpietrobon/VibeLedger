import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard_lib import apply_filters, load_transactions, sidebar_filters

st.set_page_config(page_title="Cashflow", layout="wide")
st.title("Cashflow")

try:
    df = load_transactions(st.session_state.get("db_path", ""))
except Exception:
    from dashboard_lib import DEFAULT_DB
    df = load_transactions(DEFAULT_DB)

db_path, start_d, end_d, accounts, excl_xfer = sidebar_filters(df)
f = apply_filters(df, start_d, end_d, accounts, excl_xfer)

if f.empty:
    st.warning("No transactions in this window.")
    st.stop()

f = f.copy()
f["month"] = pd.to_datetime(f["date"]).dt.strftime("%Y-%m")
f["expense"] = f["amount"].clip(lower=0)
f["income"] = (-f["amount"]).clip(lower=0)

monthly = f.groupby("month", as_index=False).agg(
    expense=("expense", "sum"),
    income=("income", "sum"),
)
monthly["net"] = monthly["income"] - monthly["expense"]

long = monthly.melt(id_vars=["month"], value_vars=["income", "expense"], var_name="kind", value_name="amount")
fig = px.bar(long, x="month", y="amount", color="kind", barmode="group", title="Monthly income vs expense")
st.plotly_chart(fig, use_container_width=True)

fig2 = px.line(monthly, x="month", y="net", markers=True, title="Net cashflow")
st.plotly_chart(fig2, use_container_width=True)

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
