"""Subscriptions & recurring payments review.

Detection is server-side and deterministic (app/services/recurring_detector.py),
surfaced via GET /analytics/recurring. This page only renders the result so the
recurring logic stays in one place.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard_lib import (
    DEFAULT_API,
    api_get,
    compact_page,
    extract_error_message,
    render_app_navigation,
    tech_sidebar,
)

st.set_page_config(page_title="Recurring", layout="wide")
compact_page()
render_app_navigation()
st.title("Subscriptions & recurring payments")
st.caption(
    "Merchants billed on a regular cadence (weekly, monthly, yearly, …), inferred "
    "from your expense history. Transfers and refunds are excluded."
)

status_choice = st.radio(
    "Show",
    ["Active", "All", "Inactive"],
    horizontal=True,
    help="Active = charged recently enough to still be live.",
)
_, api_base = tech_sidebar()
api_base = api_base or DEFAULT_API

params: dict[str, str] = {}
if status_choice == "Active":
    params["status"] = "active"
elif status_choice == "Inactive":
    params["status"] = "inactive"

resp = api_get("/analytics/recurring", params=params, base=api_base)
if not resp.ok:
    st.error(f"Failed to load recurring payments: {extract_error_message(resp)}")
    st.stop()

payload = resp.json()
items = payload.get("items", [])
summary = payload.get("summary", {})

c1, c2, c3 = st.columns(3)
c1.metric("Active subscriptions", f"{summary.get('active_count', 0):,}")
c2.metric("Est. monthly", f"${summary.get('active_monthly_estimate', 0):,.2f}")
c3.metric("Est. annual", f"${summary.get('active_annual_estimate', 0):,.2f}")
st.caption("Estimates normalize each series to a common period and cover active subscriptions only.")

if not items:
    st.info("No recurring payments detected for this filter yet.")
    st.stop()

df = pd.DataFrame(items)
df["variable"] = ~df["amount_consistent"].astype(bool)
display = df[
    [
        "merchant_label", "cadence", "average_amount", "monthly_estimate",
        "annual_estimate", "occurrences", "last_date", "next_expected_date",
        "status", "variable", "category",
    ]
].rename(
    columns={
        "merchant_label": "Merchant",
        "cadence": "Cadence",
        "average_amount": "Avg amount",
        "monthly_estimate": "Monthly",
        "annual_estimate": "Annual",
        "occurrences": "Seen",
        "last_date": "Last charge",
        "next_expected_date": "Next expected",
        "status": "Status",
        "variable": "Variable $",
        "category": "Category",
    }
)

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Avg amount": st.column_config.NumberColumn(format="$%.2f"),
        "Monthly": st.column_config.NumberColumn(format="$%.2f"),
        "Annual": st.column_config.NumberColumn(format="$%.2f"),
        "Last charge": st.column_config.DateColumn(),
        "Next expected": st.column_config.DateColumn(),
        "Variable $": st.column_config.CheckboxColumn(
            help="Amount swings between charges (e.g. a utility bill)."
        ),
    },
)
st.caption(
    "“Variable $” marks series whose amounts move between charges. Use the "
    "Transactions page to review or recategorize individual charges."
)
