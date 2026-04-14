from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard_lib import DEFAULT_DB, apply_filters, load_transactions, sidebar_filters

st.set_page_config(page_title="Categories", layout="wide")
st.title("Categories")

try:
    df = load_transactions(st.session_state.get("db_path") or DEFAULT_DB)
except Exception as e:
    st.error(f"Failed to load DB: {e}")
    st.stop()

db_path, start_d, end_d, accounts, excl_xfer = sidebar_filters(df)

if df.empty:
    st.stop()

cats = sorted(df["effective_category"].fillna("uncategorized").unique().tolist())
selected_cats = st.sidebar.multiselect("Categories", cats, default=cats, key="cats")

f = apply_filters(df, start_d, end_d, accounts, excl_xfer)
f = f[f["effective_category"].fillna("uncategorized").isin(selected_cats)]
spend = f[f["amount"] > 0].copy()

c1, c2 = st.columns(2)
with c1:
    st.metric("Transactions", len(f))
with c2:
    st.metric("Spend (positive amounts)", f"${spend['amount'].sum():,.2f}")

st.subheader("Top categories")
cat = spend.groupby("effective_category", as_index=False)["amount"].sum().sort_values("amount", ascending=False).head(20)
fig = px.bar(cat, x="amount", y="effective_category", orientation="h", title="Spend by category")
fig.update_layout(yaxis_title="Category", xaxis_title="Spend")
st.plotly_chart(fig, use_container_width=True)

st.subheader("This month vs last month")
if not spend.empty:
    today = date.today()
    first_this = today.replace(day=1)
    first_prev = (first_this - timedelta(days=1)).replace(day=1)
    last_prev = first_this - timedelta(days=1)
    m = spend.copy()
    m["bucket"] = m["date"].apply(
        lambda d: "This month" if d >= first_this else ("Last month" if first_prev <= d <= last_prev else "Other")
    )
    m = m[m["bucket"].isin(["This month", "Last month"])]
    cmp = m.groupby(["effective_category", "bucket"], as_index=False)["amount"].sum()
    top = (
        cmp.groupby("effective_category", as_index=False)["amount"].sum()
        .sort_values("amount", ascending=False)
        .head(15)["effective_category"]
    )
    cmp = cmp[cmp["effective_category"].isin(top)]
    fig2 = px.bar(cmp, x="effective_category", y="amount", color="bucket", barmode="group", title="Category comparison")
    fig2.update_xaxes(tickangle=35)
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Transaction samples by category")
if not f.empty:
    cat_pick = st.selectbox("Pick a category", sorted(f["effective_category"].fillna("uncategorized").unique().tolist()))
    samples = f[f["effective_category"].fillna("uncategorized") == cat_pick].sort_values("date", ascending=False)
    st.dataframe(
        samples[["date", "amount", "account_name", "merchant_name", "name", "plaid_category_primary", "effective_category"]].head(200),
        use_container_width=True,
        hide_index=True,
    )
