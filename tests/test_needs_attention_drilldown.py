"""Overview's "needs attention" counts must equal what their drill-downs show.

Regression guard for the bug where Overview advertised nine likely refunds and
the Transactions screen it linked to showed none. Two independent causes, both
covered here:

1. The count was a bare COUNT over `transaction_annotations`, so annotations
   orphaned by a deleted transaction inflated it.
2. The drill-down fetched one 500-row page of the newest transactions and
   narrowed it in the browser, so matches older than that page vanished.

The tests seed a ledger deliberately larger than one page with every
attention-worthy transaction among the *oldest* rows — the shape that made the
old code report "9" next to an empty list. They then run the real query string
the React screen sends, read out of the source so the assertion tracks the UI
rather than a copy of it.
"""
import re
from datetime import date, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.db.session import SessionLocal, engine
from app.db.schema_patches import apply_patches
from app.main import app
from app.models.models import (
    Account,
    CategoryDecisionEvent,
    Item,
    RejectedTransferPair,
    Transaction,
    TransactionAnnotation,
    TransferPair,
)
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS

#: bigger than the client's page size, so anything filtered client-side is lost
PAGE_SIZE = 500
FILLER_COUNT = 520

TRANSACTIONS_TSX = Path(__file__).resolve().parents[1] / "frontend/src/routes/transactions.tsx"
OVERVIEW_TSX = Path(__file__).resolve().parents[1] / "frontend/src/routes/index.tsx"

#: Overview's needs_attention key -> the ?filter= value its row links to
ATTENTION_ROWS = {
    "likely_refunds": "refunds",
    "unreviewed_transactions": "unreviewed",
    "uncategorized_transactions": "uncategorized",
}


def _ui_filter_queries() -> dict[str, str]:
    """The literal `q=` strings the Transactions screen sends per Overview filter.

    Read from the source instead of duplicated here: if someone changes the UI
    to filter a different way, this test must follow it, not keep asserting
    against a stale copy.
    """
    source = TRANSACTIONS_TSX.read_text()
    block = re.search(r"const FILTER_QUERY[^{]*\{(.*?)\n\};", source, re.S)
    assert block, (
        f"FILTER_QUERY is gone from {TRANSACTIONS_TSX.name}. The Overview drill-down "
        "must translate each filter into a server-side query; if that moved, point "
        "this test at its new home rather than deleting the check."
    )
    queries = dict(re.findall(r'(\w[\w-]*)\s*:\s*"([^"]*)"', block.group(1)))
    assert queries, "FILTER_QUERY parsed as empty"
    return queries


def _seed_ledger() -> None:
    """520 recent, tidy transactions plus older ones that need attention.

    The attention-worthy rows are the oldest in the ledger on purpose: they sit
    past the first page, where a client-side filter cannot see them.
    """
    with SessionLocal() as db:
        item = Item(plaid_item_id="i-attention", access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        checking = Account(plaid_account_id="a-chk-att", item_id=item.id, name="Checking", mask="1111")
        savings = Account(plaid_account_id="a-sav-att", item_id=item.id, name="Savings", mask="2222")
        db.add_all([checking, savings])
        db.flush()

        def txn(pid, d, amount, name, account=None, category="FOOD_AND_DRINK"):
            return Transaction(
                plaid_transaction_id=pid,
                account_id=(account or checking).id,
                item_id=item.id,
                date=d,
                amount=amount,
                name=name,
                plaid_category_primary=category,
                pending=False,
            )

        # Newest: reviewed and categorized, nothing to act on.
        filler = [
            txn(f"att-filler-{i}", date(2024, 6, 1) + timedelta(days=i), 12.0, "Coffee")
            for i in range(FILLER_COUNT)
        ]
        # Oldest: nine detected refunds awaiting confirmation.
        refunds = [
            txn(f"att-refund-{i}", date(2024, 1, 1) + timedelta(days=i), -30.0, "Returned order")
            for i in range(9)
        ]
        uncategorized = [
            txn(f"att-uncat-{i}", date(2024, 1, 15), 8.0, "Mystery charge", category=None)
            for i in range(3)
        ]
        transfer_out = txn("att-xfer-out", date(2024, 1, 20), 200.0, "Transfer", category="TRANSFER_OUT")
        transfer_in = txn("att-xfer-in", date(2024, 1, 20), -200.0, "Transfer", account=savings, category="TRANSFER_IN")

        db.add_all(filler + refunds + uncategorized + [transfer_out, transfer_in])
        db.flush()

        for t in filler:
            db.add(TransactionAnnotation(transaction_id=t.id, reviewed=True))
        for t in refunds:
            db.add(TransactionAnnotation(transaction_id=t.id, refund_status="likely", reviewed=False))
        # An unconfirmed transfer is still an accounting and review candidate;
        # it becomes excluded only after the user confirms the pair.
        db.add(TransferPair(txn_out_id=transfer_out.id, txn_in_id=transfer_in.id, confirmed=False))
        db.commit()


def _drilldown(client, query: str) -> dict:
    r = client.get(
        "/transactions",
        params={"q": query, "limit": PAGE_SIZE},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_every_attention_count_is_reproduced_by_its_drilldown():
    _seed_ledger()
    ui_queries = _ui_filter_queries()

    with TestClient(app) as client:
        overview = client.get("/analytics/overview", headers=AUTH_HEADERS).json()
        needs_attention = overview["needs_attention"]

        # Guards the fixture itself: if these stop being non-zero and older than
        # one page, the test would pass without exercising anything.
        assert needs_attention["likely_refunds"] == 9
        assert needs_attention["unreviewed_transactions"] == 14  # 9 refunds + 3 uncategorized + 2 candidates
        assert needs_attention["uncategorized_transactions"] == 3

        for key, ui_filter in ATTENTION_ROWS.items():
            count = needs_attention[key]
            assert ui_filter in ui_queries, f"Overview links to ?filter={ui_filter} with no query behind it"

            body = _drilldown(client, ui_queries[ui_filter])
            assert body["total"] == count, (
                f"Overview says {count} for {key}, but its drill-down "
                f"({ui_queries[ui_filter]!r}) matches {body['total']}"
            )
            # The reported symptom: a non-zero count linking to an empty screen.
            assert len(body["items"]) == min(count, PAGE_SIZE)

        refunds = _drilldown(client, ui_queries["refunds"])["items"]
        assert {t["refund_status"] for t in refunds} == {"likely"}
        uncategorized = _drilldown(client, ui_queries["uncategorized"])["items"]
        assert {t["effective_category"].lower() for t in uncategorized} == {"uncategorized"}
        unreviewed = _drilldown(client, ui_queries["unreviewed"])["items"]
        assert not any(t["annotation"]["reviewed"] for t in unreviewed)
        assert "att-xfer-out" in {t["plaid_transaction_id"] for t in unreviewed}


def test_overview_rows_only_link_to_filters_the_transactions_screen_implements():
    """A row pointing at an unimplemented filter renders an empty list.

    That is exactly how "Transfer pairs pending" used to behave — it linked to
    /transactions?filter=transfers, which nothing knew how to answer.
    """
    linked = set(re.findall(r'filter="([^"]+)"', OVERVIEW_TSX.read_text()))
    implemented = set(_ui_filter_queries())
    assert linked <= implemented, (
        f"Overview links to {sorted(linked - implemented)}, which the Transactions "
        "screen has no query for — those rows would open an empty list."
    )


def test_count_ignores_annotations_whose_transaction_is_gone():
    """An annotation with no transaction is invisible to every screen.

    Deleting a transaction leaves its annotation behind (nothing cascades), and
    counting those made Overview promise rows nothing could display.
    """
    _seed_ledger()

    with TestClient(app) as client:  # startup patches run here, before the orphan
        with SessionLocal() as db:
            doomed = (
                db.query(Transaction)
                .filter(Transaction.plaid_transaction_id == "att-refund-0")
                .one()
            )
            db.delete(doomed)  # annotation deliberately left behind
            db.commit()
            assert db.query(TransactionAnnotation).filter(
                TransactionAnnotation.refund_status == "likely"
            ).count() == 9

        overview = client.get("/analytics/overview", headers=AUTH_HEADERS).json()
        assert overview["needs_attention"]["likely_refunds"] == 8

        body = _drilldown(client, _ui_filter_queries()["refunds"])
        assert body["total"] == 8


def test_schema_patches_purge_orphaned_rows():
    _seed_ledger()

    with SessionLocal() as db:
        doomed = (
            db.query(Transaction)
            .filter(Transaction.plaid_transaction_id == "att-refund-1")
            .one()
        )
        survivor = (
            db.query(Transaction)
            .filter(Transaction.plaid_transaction_id == "att-refund-2")
            .one()
        )
        survivor_annotation = (
            db.query(TransactionAnnotation)
            .filter(TransactionAnnotation.transaction_id == survivor.id)
            .one()
        )
        survivor_annotation.refund_match_transaction_id = doomed.id
        survivor_annotation_id = survivor_annotation.id
        db.add(CategoryDecisionEvent(
            transaction_id=doomed.id,
            new_effective_category="FOOD/DINING",
            source="rule",
        ))
        doomed_id = doomed.id
        db.delete(doomed)
        db.commit()

    apply_patches(engine)

    with SessionLocal() as db:
        assert db.query(TransactionAnnotation).filter(
            TransactionAnnotation.transaction_id == doomed_id
        ).count() == 0
        assert db.query(CategoryDecisionEvent).filter(
            CategoryDecisionEvent.transaction_id == doomed_id
        ).count() == 0
        # A live annotation pointing at the deleted match loses the stale link
        # rather than the whole row.
        refreshed = (
            db.query(TransactionAnnotation)
            .filter(TransactionAnnotation.id == survivor_annotation_id)
            .one()
        )
        assert refreshed.refund_match_transaction_id is None
        assert refreshed.refund_status is None


def test_schema_patches_purge_orphaned_rejected_transfer_pairs():
    with SessionLocal() as db:
        item = Item(plaid_item_id="orphan-rejection", access_token_encrypted=encrypt_token("t"))
        db.add(item)
        db.flush()
        account = Account(plaid_account_id="orphan-rejection-account", item_id=item.id, name="Checking")
        db.add(account)
        db.flush()
        doomed = Transaction(
            plaid_transaction_id="orphan-rejection-doomed", account_id=account.id, item_id=item.id,
            date=date(2026, 4, 1), amount=10, name="Out",
        )
        survivor = Transaction(
            plaid_transaction_id="orphan-rejection-survivor", account_id=account.id, item_id=item.id,
            date=date(2026, 4, 2), amount=-10, name="In",
        )
        db.add_all([doomed, survivor])
        db.flush()
        db.add(RejectedTransferPair(txn_out_id=doomed.id, txn_in_id=survivor.id))
        db.commit()
        db.delete(doomed)
        db.commit()

    apply_patches(engine)

    with SessionLocal() as db:
        assert db.query(RejectedTransferPair).count() == 0
