from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from dashboard_lib import (
    DEFAULT_DB,
    category_icon,
    compact_page,
    detect_recurring,
    load_transactions,
    md_dollars,
    render_app_navigation,
    tech_sidebar,
    upcoming_bills,
)

st.set_page_config(page_title="Recurring", layout="wide")
compact_page()
render_app_navigation()
st.title("Recurring & bills")

try:
    df = load_transactions(st.session_state.get("db_path") or DEFAULT_DB)
except Exception as exc:
    st.error(f"Failed to load DB: {exc}")
    st.stop()

if df.empty:
    st.info("No transactions yet. Sync an account to detect recurring charges.")
    tech_sidebar(show_api=False)
    st.stop()

recurring = detect_recurring(df)
if recurring.empty:
    st.info(
        "No recurring charges detected yet. Detection needs at least three charges "
        "from a merchant at a regular cadence (weekly to yearly)."
    )
    tech_sidebar(show_api=False)
    st.stop()

today = min(date.today(), df["date"].max())

# Monthly-equivalent cost of each stream, so cadences are comparable.
recurring = recurring.assign(
    monthly_equiv=recurring["typical_amount"] * (30.0 / recurring["cadence_days"].clip(lower=1))
)
subscriptions = recurring[recurring["is_subscription"]]

col1, col2, col3 = st.columns(3)
col1.metric("Recurring streams", f"{len(recurring):,}")
col2.metric("Est. monthly total", f"${recurring['monthly_equiv'].sum():,.0f}")
col3.metric("Price changes", f"{recurring['price_change_pct'].notna().sum():,}")

# Price changes first — the highest-signal thing to know about your subscriptions.
changes = recurring[recurring["price_change_pct"].notna()].sort_values(
    "price_change_pct", ascending=False
)
if not changes.empty:
    st.subheader("Price changes")
    for row in changes.itertuples():
        arrow = "↑" if row.price_change_pct >= 0 else "↓"
        st.markdown(
            md_dollars(
                f":material/{category_icon(row.category)}: **{row.merchant}** "
                f"${row.prior_amount:,.2f} → ${row.last_amount:,.2f} "
                f"({arrow}{abs(row.price_change_pct):.0f}%)"
            )
        )

st.subheader("Upcoming (next 30 days)")
bills = upcoming_bills(recurring, today, horizon_days=30)
if bills.empty:
    st.caption("Nothing expected in the next 30 days.")
else:
    view = bills.assign(
        when=pd.to_datetime(bills["next_date"]).dt.date,
    )[["when", "merchant", "category", "last_amount", "cadence"]]
    st.dataframe(
        view,
        width="stretch",
        hide_index=True,
        column_config={
            "when": st.column_config.DateColumn("Expected", width="small"),
            "merchant": st.column_config.TextColumn("Merchant"),
            "category": st.column_config.TextColumn("Category"),
            "last_amount": st.column_config.NumberColumn("Amount", format="$%.2f", width="small"),
            "cadence": st.column_config.TextColumn("Cadence", width="small"),
        },
    )

st.subheader("All recurring charges")
show_subs_only = st.toggle(
    "Subscriptions only (stable amount)",
    value=False,
    help="Stable-amount streams look like true subscriptions; variable ones may be regular bills.",
)
table = subscriptions if show_subs_only else recurring
table = table.sort_values("monthly_equiv", ascending=False)
display = table.assign(last_seen=pd.to_datetime(table["last_date"]).dt.date)[
    ["merchant", "category", "cadence", "typical_amount", "monthly_equiv", "last_seen", "count"]
]
st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
    column_config={
        "merchant": st.column_config.TextColumn("Merchant"),
        "category": st.column_config.TextColumn("Category"),
        "cadence": st.column_config.TextColumn("Cadence", width="small"),
        "typical_amount": st.column_config.NumberColumn("Typical", format="$%.2f", width="small"),
        "monthly_equiv": st.column_config.NumberColumn("Monthly-equiv.", format="$%.2f", width="small"),
        "last_seen": st.column_config.DateColumn("Last seen", width="small"),
        "count": st.column_config.NumberColumn("Seen", width="small"),
    },
)

tech_sidebar(show_api=False)
