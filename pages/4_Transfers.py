import pandas as pd
import streamlit as st

from dashboard_lib import (
    DEFAULT_API,
    DEFAULT_DB,
    api_delete,
    api_post,
    load_transactions,
    load_transfer_pairs,
)

st.set_page_config(page_title="Transfers", layout="wide")
st.title("Transfer reconciliation")
st.caption(
    "Auto-matched pairs excluded from cashflow/category totals. Confirm the good ones; unpair the bad ones."
)

db_path = st.sidebar.text_input("DB path", DEFAULT_DB, key="db_path")
api_base = st.sidebar.text_input("API base", DEFAULT_API, key="api_base")

colA, colB = st.columns([1, 3])
with colA:
    if st.button("Run detection"):
        resp = api_post("/transfers/detect", json={}, base=api_base)
        if resp.ok:
            st.success(f"Detection done: {resp.json()}")
            st.cache_data.clear()
        else:
            st.error(f"Detect failed: {resp.status_code} {resp.text}")

pairs = load_transfer_pairs(db_path)

st.subheader(f"Existing pairs ({len(pairs)})")
if pairs.empty:
    st.info("No transfer pairs yet. Click 'Run detection' to scan.")
else:
    show = pairs.copy()
    show["amount"] = show["amount"].map(lambda v: f"${float(v):,.2f}")
    show = show[["id", "out_date", "in_date", "amount", "out_account", "in_account", "detected_by", "confirmed"]]
    st.dataframe(show, use_container_width=True, hide_index=True)

    selected_id = st.selectbox("Select pair id for action", pairs["id"].tolist())
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Confirm"):
            resp = api_post(f"/transfers/{int(selected_id)}/confirm", base=api_base)
            if resp.ok:
                st.success("Confirmed.")
                st.cache_data.clear()
            else:
                st.error(f"{resp.status_code} {resp.text}")
    with c2:
        if st.button("Unpair"):
            resp = api_delete(f"/transfers/{int(selected_id)}", base=api_base)
            if resp.ok:
                st.success("Unpaired.")
                st.cache_data.clear()
            else:
                st.error(f"{resp.status_code} {resp.text}")

st.divider()
st.subheader("Manual pair")
txns = load_transactions(db_path)
if not txns.empty:
    unpaired = txns[~txns.get("is_transfer", False)]
    unpaired = unpaired.sort_values("date", ascending=False).head(500)
    unpaired["label"] = unpaired.apply(
        lambda r: f"#{int(r['id'])} {r['date']} {r['account_name']} ${float(r['amount']):,.2f} — {r['name']}",
        axis=1,
    )
    a = st.selectbox("Transaction A (outflow, amount > 0)", unpaired["label"].tolist(), key="manual_a")
    b = st.selectbox("Transaction B (inflow, amount < 0)", unpaired["label"].tolist(), key="manual_b")
    if st.button("Pair A + B"):
        aid = int(a.split()[0].lstrip("#"))
        bid = int(b.split()[0].lstrip("#"))
        resp = api_post("/transfers", json={"txn_a_id": aid, "txn_b_id": bid}, base=api_base)
        if resp.ok:
            st.success("Paired.")
            st.cache_data.clear()
        else:
            st.error(f"{resp.status_code} {resp.text}")
