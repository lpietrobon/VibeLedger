from __future__ import annotations

import calendar
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from dashboard_lib import (
    DEFAULT_DB,
    compact_page,
    load_accounts,
    load_transactions,
    overview_period_summary,
    render_app_navigation,
    spend_transactions,
    tech_sidebar,
)

st.set_page_config(page_title="VibeLedger Overview", layout="wide")
compact_page()
render_app_navigation()
st.title("Overview")

db_path = st.session_state.get("db_path") or DEFAULT_DB

try:
    transactions = load_transactions(db_path)
    accounts = load_accounts(db_path)
except Exception as exc:
    st.error(f"Failed to load VibeLedger data: {exc}")
    tech_sidebar()
    st.stop()

if transactions.empty:
    st.info("No transactions yet. Connect or sync an account to populate the overview.")
    tech_sidebar()
    st.stop()

today = min(date.today(), transactions["date"].max())
current_start = today.replace(day=1)
previous_end = current_start - timedelta(days=1)
previous_start = previous_end.replace(day=1)

summary = overview_period_summary(
    transactions[~transactions["is_transfer"]],
    current_start,
    today,
    previous_start,
    previous_end,
)

assets = liabilities = 0.0
if not accounts.empty:
    balances = pd.to_numeric(accounts["current_balance"], errors="coerce").fillna(0.0)
    assets = float(balances[accounts["type"].isin({"depository", "investment", "brokerage"})].sum())
    liabilities = float(balances[accounts["type"].isin({"credit", "loan"})].sum())
net_worth = assets - liabilities

spend_delta_pct = None
if summary["previous_spend"]:
    spend_delta_pct = summary["spend_change"] / summary["previous_spend"] * 100

st.caption(f"Through {today:%B %-d, %Y}")
spend_delta_text = (
    f"{spend_delta_pct:+.1f}% vs last month"
    if spend_delta_pct is not None
    else "No prior comparison"
)
st.markdown(
    f"""
    <style>
    .overview-metric-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: .7rem;
        margin: .25rem 0 .8rem;
    }}
    .overview-metric {{
        border: 1px solid rgba(128,128,128,.22);
        border-radius: .7rem;
        padding: .65rem .75rem;
        min-width: 0;
    }}
    .overview-metric-label {{ font-size: .78rem; opacity: .72; }}
    .overview-metric-value {{ font-size: 1.45rem; font-weight: 650; line-height: 1.2; }}
    .overview-metric-note {{ font-size: .72rem; opacity: .68; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    @media (max-width: 768px) {{
        .overview-metric-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .45rem; }}
        .overview-metric {{ padding: .5rem .6rem; }}
        .overview-metric-value {{ font-size: 1.2rem; }}
    }}
    </style>
    <div class="overview-metric-grid">
      <div class="overview-metric"><div class="overview-metric-label">Net worth</div><div class="overview-metric-value">${net_worth:,.0f}</div></div>
      <div class="overview-metric"><div class="overview-metric-label">Month spending</div><div class="overview-metric-value">${summary['spend']:,.0f}</div><div class="overview-metric-note">{spend_delta_text}</div></div>
      <div class="overview-metric"><div class="overview-metric-label">Month income</div><div class="overview-metric-value">${summary['income']:,.0f}</div></div>
      <div class="overview-metric"><div class="overview-metric-label">Net cashflow</div><div class="overview-metric-value">${summary['net']:,.0f}</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([3, 2])
with left:
    st.subheader("What changed")
    current_spend = spend_transactions(
        transactions[
            (transactions["date"] >= current_start)
            & (transactions["date"] <= today)
            & (~transactions["is_transfer"])
        ]
    )
    previous_spend = spend_transactions(
        transactions[
            (transactions["date"] >= previous_start)
            & (transactions["date"] <= previous_end)
            & (~transactions["is_transfer"])
        ]
    )

    def category_totals(frame: pd.DataFrame, value_name: str) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(columns=["category", value_name])
        category = (
            frame["effective_category"]
            .fillna("Uncategorized")
            .astype(str)
            .str.split("/")
            .str[0]
            .str.strip()
            .replace("", "Uncategorized")
        )
        return (
            frame.assign(category=category)
            .groupby("category", as_index=False)["amount"]
            .sum()
            .rename(columns={"amount": value_name})
        )

    movers = category_totals(current_spend, "current").merge(
        category_totals(previous_spend, "previous"),
        on="category",
        how="outer",
    ).fillna(0)
    movers["change"] = movers["current"] - movers["previous"]
    movers = movers.sort_values("change", ascending=False).head(5)

    if movers.empty:
        st.caption("No spending changes to show yet.")
    else:
        for row in movers.itertuples():
            st.markdown(
                f"**{row.category}** · ${row.current:,.0f} "
                f"({'+' if row.change >= 0 else '−'}${abs(row.change):,.0f})"
            )

    if summary["top_driver"]:
        driver = summary["top_driver"]
        st.caption(f"Top current-month driver: {driver['category']} at ${driver['amount']:,.0f}.")

    st.page_link("pages/2_Spending.py", label="Explore spending", icon=":material/arrow_forward:")

with right:
    st.subheader("Needs attention")
    needs_review = transactions[
        (~transactions["is_transfer"])
        & (~transactions["reviewed"].fillna(False).astype(bool))
    ].sort_values("date", ascending=False)
    uncategorized = transactions[
        transactions["effective_category"].fillna("uncategorized").str.lower().eq("uncategorized")
    ]
    st.metric("Unreviewed transactions", f"{len(needs_review):,}")
    st.metric("Uncategorized transactions", f"{len(uncategorized):,}")
    st.page_link("pages/6_Transactions.py", label="Review transactions", icon=":material/arrow_forward:")

st.subheader("Recent transactions")
recent = transactions[~transactions["is_transfer"]].sort_values("date", ascending=False).head(8)
recent_cols = ["date", "effective_merchant", "effective_category", "amount"]
st.dataframe(
    recent[recent_cols],
    use_container_width=True,
    hide_index=True,
    column_config={
        "date": st.column_config.DateColumn("Date", width="small"),
        "effective_merchant": st.column_config.TextColumn("Merchant"),
        "effective_category": st.column_config.TextColumn("Category"),
        "amount": st.column_config.NumberColumn("Amount", format="$%.2f", width="small"),
    },
)

tech_sidebar()
