import streamlit as st

from dashboard_lib import (
    DEFAULT_API,
    apply_filters,
    load_accounts,
    load_transactions,
    load_transfer_pairs,
    sidebar_filters,
)

st.set_page_config(page_title="VibeLedger", layout="wide")
st.title("VibeLedger")
st.caption("Consolidated multi-account view. Use the sidebar pages for details.")

try:
    df = load_transactions(st.session_state.get("db_path", "")) if st.session_state.get("db_path") else load_transactions(__import__("dashboard_lib").DEFAULT_DB)
except Exception as e:
    st.error(f"Failed to load DB: {e}")
    st.stop()

db_path, start_d, end_d, accounts, excl_xfer = sidebar_filters(df)

if df.empty:
    st.warning("No transactions in DB yet. Link an account and sync first.")
    st.stop()

f = apply_filters(df, start_d, end_d, accounts, excl_xfer)

col1, col2, col3, col4 = st.columns(4)
spend = f[f["amount"] > 0]["amount"].sum()
income = -f[f["amount"] < 0]["amount"].sum()
net = income - spend
with col1:
    st.metric("Transactions", len(f))
with col2:
    st.metric("Spend", f"${spend:,.2f}")
with col3:
    st.metric("Income", f"${income:,.2f}")
with col4:
    st.metric("Net", f"${net:,.2f}")

accounts_df = load_accounts(db_path)
pairs_df = load_transfer_pairs(db_path)

st.subheader("At a glance")
c1, c2 = st.columns(2)
with c1:
    st.write(f"**Accounts linked:** {len(accounts_df)}")
    st.write(f"**Transfer pairs detected:** {len(pairs_df)} ({(pairs_df['confirmed']==1).sum() if not pairs_df.empty else 0} confirmed)")
with c2:
    st.write(f"**API base:** `{DEFAULT_API}`")
    st.write("**Pages:** Accounts · Cashflow · Categories · Transfers")

st.info("Jump into a page from the left sidebar for deeper views.")
