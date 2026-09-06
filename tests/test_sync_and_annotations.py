from datetime import date

from fastapi.testclient import TestClient
from app.db.session import SessionLocal
from app.main import app
from app.models.models import (
    Account,
    AnnotationFingerprint,
    CategoryDecisionEvent,
    Item,
    RejectedTransferPair,
    Transaction,
    TransactionAnnotation,
    TransferPair,
)
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
        db.add(Item(plaid_item_id="all-1", access_token_encrypted=encrypt_token("tok-1"), status="active"))
        db.add(Item(plaid_item_id="all-2", access_token_encrypted=encrypt_token("tok-2"), status="active"))
        db.commit()

    with TestClient(app) as client:
        r = client.post('/sync/all', headers=AUTH_HEADERS)
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == "2/2 items synced"
    assert len(body["results"]) == 2
    assert all(res["status"] == "success" for res in body["results"])


def test_item_removal_cleans_rejections_and_detaches_retained_fingerprint():
    """A relink can restore the fingerprint, but no deleted transaction IDs remain live."""
    with SessionLocal() as db:
        old_item = Item(plaid_item_id="remove-old", access_token_encrypted=encrypt_token("old"), status="active")
        other_item = Item(plaid_item_id="remove-other", access_token_encrypted=encrypt_token("other"), status="active")
        db.add_all([old_item, other_item])
        db.flush()
        old_account = Account(plaid_account_id="remove-old-account", item_id=old_item.id, name="Old")
        other_account = Account(plaid_account_id="remove-other-account", item_id=other_item.id, name="Other")
        db.add_all([old_account, other_account])
        db.flush()
        doomed = Transaction(
            plaid_transaction_id="remove-doomed", account_id=old_account.id, item_id=old_item.id,
            date=date(2026, 4, 10), amount=25, name="Original",
        )
        survivor = Transaction(
            plaid_transaction_id="remove-survivor", account_id=other_account.id, item_id=other_item.id,
            date=date(2026, 4, 11), amount=-25, name="Counterparty",
        )
        db.add_all([doomed, survivor])
        db.flush()
        db.add_all([
            TransactionAnnotation(transaction_id=doomed.id, notes="retain through relink"),
            TransactionAnnotation(
                transaction_id=survivor.id,
                refund_status="likely",
                refund_match_transaction_id=doomed.id,
            ),
            TransferPair(txn_out_id=doomed.id, txn_in_id=survivor.id),
            RejectedTransferPair(txn_out_id=doomed.id, txn_in_id=survivor.id),
            CategoryDecisionEvent(transaction_id=doomed.id, new_effective_category="FOOD/DINING", source="manual"),
            AnnotationFingerprint(
                txn_hash="remove-fingerprint", txn_occurrence=0, account_mask="1111",
                txn_date=date(2026, 4, 10), amount=25, name="Original",
                source_transaction_id=doomed.id, applied_transaction_id=doomed.id,
            ),
        ])
        db.commit()
        old_item_id = old_item.id
        doomed_id = doomed.id
        survivor_id = survivor.id

    with TestClient(app) as client:
        response = client.post(f"/items/{old_item_id}/remove", headers=AUTH_HEADERS)
    assert response.status_code == 200

    with SessionLocal() as db:
        assert db.get(Transaction, doomed_id) is None
        assert db.query(TransferPair).count() == 0
        assert db.query(RejectedTransferPair).count() == 0
        assert db.query(CategoryDecisionEvent).filter_by(transaction_id=doomed_id).count() == 0
        survivor_annotation = db.query(TransactionAnnotation).filter_by(transaction_id=survivor_id).one()
        assert survivor_annotation.refund_match_transaction_id is None
        assert db.query(AnnotationFingerprint).one().applied_transaction_id is None
