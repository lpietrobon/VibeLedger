import streamlit as st

from dashboard_lib import compact_page

st.set_page_config(page_title="Debt and Cash Runway", layout="wide")
compact_page()
st.title("Debt and cash runway")
st.info("TODO — this page is a placeholder while the underlying model and goals are designed.")

st.markdown(
    """
This view should eventually help answer:

- How quickly are debts being paid down?
- What is the projected payoff date at the current payment pace?
- How many months of normal spending can available cash cover?
- How does cash compare with an emergency-fund target?
- Which balances should count as liquid cash, debt, or long-term assets?

Before building the charts, VibeLedger needs reliable historical balances plus user-defined targets
and account classifications. The presentation could then combine debt balance trends, payoff
projections, cash runway, and an emergency-fund target band.
"""
)
