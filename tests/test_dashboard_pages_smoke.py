"""Headless render test for every dashboard page against a seeded DB.

Uses Streamlit's AppTest to execute each page top-to-bottom and assert it renders
without raising. st.page_link needs the full multipage page-graph (which AppTest
does not build), so it is stubbed to a no-op — this exercises the real page body
(detection, charts, tables) without the harness limitation. Skipped automatically
if the dashboard extra (streamlit) is not installed.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from app.db.schema_patches import apply_patches
from app.models.models import (
    Account,
    AccountBalanceSnapshot,
    Base,
    Item,
    Transaction,
    TransactionAnnotation,
)

PAGES = [
    "Spend.py",
    "pages/1_Accounts.py",
    "pages/2_Cashflow.py",
    "pages/2_Spending.py",
    "pages/3_Cashflow_Sankey.py",
    "pages/6_Transactions.py",
    "pages/8_Recurring.py",
]


@pytest.fixture(scope="module")
def seeded_db(tmp_path_factory) -> str:
    db_path = str(tmp_path_factory.mktemp("dash") / "smoke.db")
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    apply_patches(engine)
    today = date(2026, 7, 1)

    with Session(engine) as s:
        s.add(Item(id=1, plaid_item_id="i1", access_token_encrypted="x",
                   institution_name="Chase", status="active"))
        for aid, name, mask, typ, sub, bal in [
            (1, "Checking", "0001", "depository", "checking", 5200.0),
            (2, "Sapphire", "0003", "credit", "credit card", 1400.0),
            (3, "Brokerage", "0004", "investment", "brokerage", 42000.0),
        ]:
            s.add(Account(id=aid, plaid_account_id=f"a{aid}", item_id=1, name=name,
                          mask=mask, type=typ, subtype=sub, current_balance=bal, currency="USD"))
        s.flush()

        for i in range(60, -1, -3):
            d = today - timedelta(days=i)
            for aid, base in [(1, 5000), (2, 1500), (3, 40000)]:
                s.add(AccountBalanceSnapshot(account_id=aid, as_of_date=d,
                                             current_balance=base + (60 - i) * 15, source="accounts_get"))

        tid = 0

        def tx(acct, d, amt, name, merchant, cat):
            nonlocal tid
            tid += 1
            s.add(Transaction(id=tid, plaid_transaction_id=f"t{tid}", account_id=acct, item_id=1,
                              date=d, amount=amt, name=name, merchant_name=merchant,
                              plaid_category_primary=cat, pending=False, raw_json="{}"))
            s.add(TransactionAnnotation(transaction_id=tid, reviewed=False))

        for i in range(6):  # Netflix with a price hike on the latest charge
            tx(2, today - timedelta(days=30 * (5 - i)), 15.49 if i < 5 else 17.99,
               "NETFLIX", "Netflix", "ENTERTAINMENT")
        # Monthly insurance whose next charge lands ~10 days out (drives "Upcoming bills").
        for i in range(5):
            tx(1, date(2026, 2, 10) + timedelta(days=30 * i), 120.0,
               "ACME INSURANCE", "Acme Insurance", "GENERAL_SERVICES")
        for i in range(20):  # routine varied spend
            tx(1, today - timedelta(days=i * 3 + 1), 20.0 + i, "WHOLE FOODS", "Whole Foods", "FOOD_AND_DRINK")
        tx(1, today - timedelta(days=1), 620.0, "WIRE OUT", None, None)  # large uncategorized
        for i in range(6):  # income
            tx(1, today - timedelta(days=30 * (5 - i)), -5200.0, "PAYROLL", "Employer", "INCOME")
        s.commit()

    return db_path


def _run(page: str, db_path: str) -> AppTest:
    import streamlit as st

    st.page_link = lambda *a, **k: None  # AppTest has no page-graph; stub the links
    at = AppTest.from_file(page, default_timeout=60)
    at.session_state["db_path"] = db_path
    at.run()
    return at


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_exception(page, seeded_db):
    at = _run(page, seeded_db)
    assert not at.exception, f"{page} raised: {[repr(e.value) for e in at.exception]}"


def _all_text(at: AppTest) -> str:
    parts: list[str] = []
    for kind in ("markdown", "title", "header", "subheader", "caption", "success", "info"):
        try:
            parts.extend(el.value for el in getattr(at, kind))
        except Exception:
            pass
    return " ".join(parts)


def test_overview_surfaces_anomalies_and_bills(seeded_db):
    at = _run("Spend.py", seeded_db)
    text = _all_text(at)
    assert "worth a look" in text  # anomaly attention list rendered
    assert "Upcoming bills" in text  # detected recurring charge surfaced


def test_recurring_page_flags_price_change(seeded_db):
    at = _run("pages/8_Recurring.py", seeded_db)
    text = _all_text(at)
    assert "Netflix" in text
    assert "Price changes" in text


def test_accounts_page_has_net_worth_headline(seeded_db):
    at = _run("pages/1_Accounts.py", seeded_db)
    assert "Net worth" in _all_text(at)
