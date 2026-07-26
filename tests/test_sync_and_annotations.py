from fastapi.testclient import TestClient
from app.db.session import SessionLocal
from app.main import app
from app.models.models import Item
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def test_sync_missing_item_returns_404():
    with TestClient(app) as client:
        r = client.post('/sync/item/999999', headers=AUTH_HEADERS)
    assert r.status_code == 404


def test_annotation_missing_transaction_404():
    with TestClient(app) as client:
        r = client.patch('/transactions/999999/annotation', json={'notes': 'x'}, headers=AUTH_HEADERS)
    assert r.status_code == 404


def test_sync_all_no_items():
    with TestClient(app) as client:
        r = client.post('/sync/all', headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json()["summary"] == "no active items"


def test_sync_all_syncs_active_items():
    with SessionLocal() as db:
        db.add(Item(plaid_item_id="all-1", access_token_encrypted=encrypt_token("tok"), status="active"))
        db.add(Item(plaid_item_id="all-2", access_token_encrypted=encrypt_token("tok"), status="active"))
        db.commit()

    with TestClient(app) as client:
        r = client.post('/sync/all', headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == "2/2 items synced"
    assert len(body["results"]) == 2
    assert all(res["status"] == "success" for res in body["results"])


def test_unapplied_fingerprints_include_ones_whose_transaction_is_gone():
    """"Unapplied" has to mean "no live transaction carries it".

    A fingerprint keeps its applied_transaction_id when the transaction is
    deleted, so an IS NULL check hides exactly the annotations this endpoint
    exists to surface after an item re-link.
    """
    from datetime import date

    from app.core.time import utcnow
    from app.models.models import Account, AnnotationFingerprint, Transaction

    with SessionLocal() as db:
        item = Item(plaid_item_id="i-fp", access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        account = Account(plaid_account_id="a-fp", item_id=item.id, name="Checking", mask="9999")
        db.add(account)
        db.flush()

        live = Transaction(
            plaid_transaction_id="fp-live", account_id=account.id, item_id=item.id,
            date=date(2026, 2, 2), amount=15.0, name="Kept",
        )
        doomed = Transaction(
            plaid_transaction_id="fp-doomed", account_id=account.id, item_id=item.id,
            date=date(2026, 2, 3), amount=25.0, name="Removed",
        )
        db.add_all([live, doomed])
        db.flush()

        for txn, h in ((live, "hash-live"), (doomed, "hash-doomed")):
            db.add(AnnotationFingerprint(
                txn_hash=h,
                txn_occurrence=0,
                account_mask="9999",
                txn_date=txn.date,
                amount=txn.amount,
                name=txn.name,
                user_category="SHOPPING/GENERAL",
                source_transaction_id=txn.id,
                applied_transaction_id=txn.id,
                applied_at=utcnow(),
            ))
        db.commit()

    with TestClient(app) as client:
        assert client.get(
            "/annotations/fingerprints", params={"unapplied_only": True}, headers=AUTH_HEADERS
        ).json() == []

        with SessionLocal() as db:
            db.query(Transaction).filter(Transaction.plaid_transaction_id == "fp-doomed").delete()
            db.commit()

        unapplied = client.get(
            "/annotations/fingerprints", params={"unapplied_only": True}, headers=AUTH_HEADERS
        ).json()
        assert [f["txn_hash"] for f in unapplied] == ["hash-doomed"]
        assert len(client.get("/annotations/fingerprints", headers=AUTH_HEADERS).json()) == 2


def test_remove_item_leaves_no_rows_pointing_at_deleted_transactions():
    """The documented re-link workflow runs through here.

    Anything left pointing at a removed transaction is invisible to joins but
    still counted by aggregates, and SQLite reuses rowids — so a leftover row
    can later attach itself to an unrelated transaction.
    """
    from datetime import date

    from app.core.time import utcnow
    from app.models.models import (
        Account,
        AnnotationFingerprint,
        CategoryDecisionEvent,
        RejectedTransferPair,
        Transaction,
        TransactionAnnotation,
        TransferPair,
    )

    with SessionLocal() as db:
        item = Item(plaid_item_id="i-rm", access_token_encrypted=encrypt_token("t"), status="active")
        keeper = Item(plaid_item_id="i-keep", access_token_encrypted=encrypt_token("t"), status="active")
        db.add_all([item, keeper])
        db.flush()
        account = Account(plaid_account_id="a-rm", item_id=item.id, name="Checking", mask="4444")
        kept_account = Account(plaid_account_id="a-keep", item_id=keeper.id, name="Savings", mask="5555")
        db.add_all([account, kept_account])
        db.flush()

        charge = Transaction(
            plaid_transaction_id="rm-charge", account_id=account.id, item_id=item.id,
            date=date(2026, 3, 1), amount=60.0, name="Store",
        )
        survivor = Transaction(
            plaid_transaction_id="rm-survivor", account_id=kept_account.id, item_id=keeper.id,
            date=date(2026, 3, 4), amount=-60.0, name="Store refund",
        )
        db.add_all([charge, survivor])
        db.flush()

        db.add(TransactionAnnotation(transaction_id=charge.id, user_category="SHOPPING/GENERAL"))
        db.add(TransactionAnnotation(
            transaction_id=survivor.id,
            refund_status="likely",
            refund_match_transaction_id=charge.id,
            refund_reason="Exact account, amount, and transaction-name match",
        ))
        db.add(TransferPair(txn_out_id=charge.id, txn_in_id=survivor.id))
        db.add(RejectedTransferPair(txn_out_id=charge.id, txn_in_id=survivor.id))
        db.add(CategoryDecisionEvent(
            transaction_id=charge.id, new_effective_category="SHOPPING/GENERAL", source="manual",
        ))
        db.add(AnnotationFingerprint(
            txn_hash="hash-rm", txn_occurrence=0, account_mask="4444",
            txn_date=charge.date, amount=charge.amount, name=charge.name,
            user_category="SHOPPING/GENERAL",
            source_transaction_id=charge.id, applied_transaction_id=charge.id,
            applied_at=utcnow(),
        ))
        db.commit()
        removed_item_id, removed_txn_id, survivor_id = item.id, charge.id, survivor.id

    with TestClient(app) as client:
        r = client.post(f"/items/{removed_item_id}/remove", headers=AUTH_HEADERS)
        assert r.status_code == 200

        with SessionLocal() as db:
            assert db.query(Transaction).filter(Transaction.id == removed_txn_id).count() == 0
            assert db.query(TransactionAnnotation).filter(
                TransactionAnnotation.transaction_id == removed_txn_id
            ).count() == 0
            assert db.query(TransferPair).count() == 0
            assert db.query(CategoryDecisionEvent).count() == 0
            # A surviving rejection would suppress a future pairing between
            # whichever transactions inherit these rowids.
            assert db.query(RejectedTransferPair).count() == 0

            refund = db.query(TransactionAnnotation).filter(
                TransactionAnnotation.transaction_id == survivor_id
            ).one()
            assert refund.refund_match_transaction_id is None
            assert refund.refund_status is None

            # The fingerprint is the whole point of the re-link flow: it stays,
            # but stops claiming a transaction that no longer exists.
            fingerprint = db.query(AnnotationFingerprint).one()
            assert fingerprint.user_category == "SHOPPING/GENERAL"
            assert fingerprint.applied_transaction_id is None

        assert client.get(
            "/annotations/fingerprints", params={"unapplied_only": True}, headers=AUTH_HEADERS
        ).json()[0]["txn_hash"] == "hash-rm"

        overview = client.get("/analytics/overview", headers=AUTH_HEADERS).json()
        assert overview["needs_attention"]["likely_refunds"] == 0
        assert overview["needs_attention"]["transfer_pairs_pending"] == 0
