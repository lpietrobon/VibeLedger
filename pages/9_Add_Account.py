"""Link a new bank account through Plaid.

Creates a short-lived connect session via POST /connect/sessions and hands the
user the resulting URL, which serves Plaid Link in the browser. Completion is
handled by the unauthenticated /connect/complete callback (see app/api/routes.py
and the connect flow in CLAUDE.md).
"""
from __future__ import annotations

import streamlit as st

from dashboard_lib import (
    DEFAULT_API,
    api_get,
    api_post,
    compact_page,
    extract_error_message,
    render_app_navigation,
    tech_sidebar,
)

st.set_page_config(page_title="Add account", layout="wide")
compact_page()
render_app_navigation()
st.title("Add a bank account")
st.caption("Generate a secure Plaid link, connect your bank in the browser, then sync.")

_, api_base = tech_sidebar()
api_base = api_base or DEFAULT_API

st.markdown(
    """
    1. **Generate a link** — creates a one-time secure session (valid 20 minutes).
    2. **Open Plaid Link** — connect your bank in a new browser tab.
    3. **Sync** — pull the new account's balances and transactions.
    """
)

if st.button("Generate secure link", type="primary"):
    resp = api_post("/connect/sessions", json={"user_id": "default-user"}, base=api_base)
    if resp.ok:
        st.session_state["connect_session"] = resp.json()
    else:
        st.session_state.pop("connect_session", None)
        st.error(f"Could not create a connect session: {extract_error_message(resp)}")

session = st.session_state.get("connect_session")
if session:
    st.divider()
    st.link_button("Open Plaid Link ↗", session["connect_url"], type="primary")
    st.caption(f"Link expires at {session.get('expires_at', 'soon')}. Opens in a new tab.")
    st.code(session["connect_url"], language=None)
    st.info(
        "OAuth banks (large national institutions) need `PLAID_REDIRECT_URI` reachable "
        "publicly — wrap the flow with `scripts/connect_funnel.sh`. Sandbox and "
        "non-OAuth institutions work over the tailnet directly.",
        icon=":material/info:",
    )

    if st.button("I've finished linking — check status"):
        status_resp = api_get(f"/connect/sessions/{session['session_token']}", base=api_base)
        if status_resp.ok:
            data = status_resp.json()
            if data.get("status") == "completed":
                st.success(f"Linked! Plaid item: {data.get('item_id')}")
            else:
                st.warning(f"Session status: {data.get('status')}. Complete Plaid Link, then re-check.")
        else:
            st.error(f"Status check failed: {extract_error_message(status_resp)}")

st.divider()
st.subheader("Sync accounts")
st.caption("After linking, sync to pull balances and transaction history (backfill can take a few minutes).")
if st.button("Sync all accounts"):
    sync_resp = api_post("/sync/all", base=api_base)
    if sync_resp.ok:
        st.success(sync_resp.json().get("summary", "Sync complete."))
        st.cache_data.clear()
    else:
        st.error(f"Sync failed: {extract_error_message(sync_resp)}")
