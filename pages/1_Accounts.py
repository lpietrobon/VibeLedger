import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard_lib import (
    DEFAULT_API,
    DEFAULT_DB,
    api_patch,
    compact_page,
    extract_error_message,
    is_dark_theme,
    load_accounts,
    load_balance_snapshots,
    md_dollars,
    net_worth_headline,
    net_worth_timeseries,
    render_app_navigation,
)

st.set_page_config(page_title="Accounts", layout="wide")
compact_page()
render_app_navigation()
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

# Net worth over time — accrues from the daily balance snapshot each sync writes.
try:
    snapshots = load_balance_snapshots(db_path)
except Exception:
    snapshots = pd.DataFrame()
networth = net_worth_timeseries(snapshots, accounts) if not snapshots.empty else pd.DataFrame()

st.subheader("Net worth over time")
if len(networth) < 2:
    st.caption(
        "Balance history is still building — one snapshot is captured per account on "
        "each sync, so the trend fills in over the coming days."
    )
else:
    st.markdown("#### " + md_dollars(net_worth_headline(networth)))
    dark = is_dark_theme()
    nw_fig = go.Figure()
    nw_fig.add_trace(
        go.Scatter(
            x=networth["date"],
            y=networth["net_worth"],
            name="Net worth",
            mode="lines",
            fill="tozeroy",
            line={"color": "#2a78d6" if not dark else "#3987e5", "width": 2},
            fillcolor="rgba(42,120,214,0.18)",
        )
    )
    nw_fig.update_layout(
        hovermode="x unified",
        showlegend=False,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        height=280,
        yaxis={"tickprefix": "$"},
        xaxis_title=None,
        yaxis_title=None,
    )
    st.plotly_chart(nw_fig, width="stretch")

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
