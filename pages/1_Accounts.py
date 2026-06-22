import pandas as pd
import streamlit as st

from dashboard_lib import DEFAULT_API, DEFAULT_DB, api_patch, compact_page, extract_error_message, load_accounts

st.set_page_config(page_title="Accounts", layout="wide")
compact_page()
st.title("Accounts Summary")

with st.sidebar.expander("Connection settings", expanded=False):
    db_path = st.text_input("DB path", DEFAULT_DB, key="db_path")
    api_base = st.text_input("API base", DEFAULT_API, key="api_base")

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
    for _, row in group.iterrows():
        acct_id = int(row["id"])
        display_name = row.get("effective_account_name") or row["name"]
        bal = f"${float(row['current_balance']):,.2f}"

        with st.expander(f"{display_name}  —  {bal}", expanded=False):
            st.write(f"**Raw name:** {row['name']}  ·  **Mask:** ···{row['mask']}  ·  **Subtype:** {row['subtype']}")
            if row.get("institution_name"):
                st.write(f"**Institution:** {row['institution_name']}")

            with st.form(f"nickname_form_{acct_id}"):
                new_nick = st.text_input(
                    "Nickname",
                    value=row.get("nickname") or "",
                    placeholder="e.g. Chase Sapphire, Citi Double Cash",
                )
                save = st.form_submit_button("Save nickname")

            if save:
                resp = api_patch(
                    f"/accounts/{acct_id}",
                    json={"nickname": new_nick.strip() or None},
                    base=api_base,
                )
                if resp.ok:
                    st.success("Saved.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"Failed: {extract_error_message(resp)}")

    subtotal = group["current_balance"].sum()
    st.caption(f"Subtotal: ${subtotal:,.2f}")
