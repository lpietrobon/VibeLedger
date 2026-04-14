import pandas as pd
import streamlit as st

from dashboard_lib import DEFAULT_DB, load_accounts

st.set_page_config(page_title="Accounts", layout="wide")
st.title("Accounts Summary")

db_path = st.sidebar.text_input("DB path", DEFAULT_DB, key="db_path")

try:
    accounts = load_accounts(db_path)
except Exception as e:
    st.error(f"Failed to load DB: {e}")
    st.stop()

if accounts.empty:
    st.warning("No accounts linked yet.")
    st.stop()

accounts["current_balance"] = pd.to_numeric(accounts["current_balance"], errors="coerce").fillna(0.0)

ASSET_TYPES = {"depository", "investment", "brokerage"}
LIABILITY_TYPES = {"credit", "loan"}

assets = accounts[accounts["type"].isin(ASSET_TYPES)]["current_balance"].sum()
liab = accounts[accounts["type"].isin(LIABILITY_TYPES)]["current_balance"].sum()
net = assets - liab

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Assets", f"${assets:,.2f}")
with c2:
    st.metric("Liabilities", f"${liab:,.2f}")
with c3:
    st.metric("Net worth (est.)", f"${net:,.2f}")
st.caption("Assets = depository/investment balances. Liabilities = credit + loan balances (positive = owed).")

for type_name, group in accounts.groupby(accounts["type"].fillna("other")):
    st.subheader(f"{type_name} ({len(group)})")
    cols = ["name", "mask", "subtype", "institution_name", "current_balance", "available_balance", "credit_limit", "currency"]
    view = group[cols].copy()
    view["current_balance"] = view["current_balance"].map(lambda v: f"${v:,.2f}")
    st.dataframe(view, use_container_width=True, hide_index=True)
    subtotal = group["current_balance"].sum()
    st.caption(f"Subtotal: ${subtotal:,.2f}")
