"""Frozen PI-30 contract for variable-description confirmed-route reconciliation.

All fixtures in this module are synthetic.  A historical manual decision may
teach exactly one directed account route only when one provider description is
stable and the other changes solely in a bounded numeric reference token.  It
must not become fuzzy description matching or a route-wide allowlist.
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction, TransferPair
from app.services import transfer_detector
from app.services.security import encrypt_token
from app.services.sync_service import SyncService
from tests.conftest import AUTH_HEADERS


DETAIL_PAYMENT = "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"
DETAIL_WAGES = "INCOME_WAGES"
BOUNDS = {"start_date": "2034-01-01", "end_date": "2034-01-31"}


def _detail(value: str | None) -> str | None:
    return json.dumps({"personal_finance_category": {"detailed": value}}) if value else None


def _setup():
    db = SessionLocal()
    item = Item(
        plaid_item_id="pi30-item", access_token_encrypted=encrypt_token("synthetic"), status="active"
    )
    db.add(item)
    db.flush()
    checking = Account(
        plaid_account_id="pi30-checking", item_id=item.id, name="Synthetic checking",
        type="depository", subtype="checking", currency="USD",
    )
    card = Account(
        plaid_account_id="pi30-card", item_id=item.id, name="Synthetic card",
        type="credit", subtype="credit card", currency="USD",
    )
    alternate = Account(
        plaid_account_id="pi30-alternate", item_id=item.id, name="Synthetic alternate",
        type="depository", subtype="checking", currency="USD",
    )
    db.add_all([checking, card, alternate])
    db.flush()
    return db, item, checking, card, alternate


def _txn(db, item, account, key, when, amount, name, detail):
    txn = Transaction(
        plaid_transaction_id=f"pi30-{key}", item_id=item.id, account_id=account.id,
        date=when, amount=Decimal(str(amount)), name=name, raw_json=_detail(detail), pending=False,
    )
    db.add(txn)
    db.flush()
    return txn


def _history(db, item, checking, card, *, out_name="AUTOPAY CARD REF 1001", in_name="CARD PAYMENT RECEIVED"):
    old_out = _txn(db, item, checking, "old-out", date(2034, 1, 2), 41, out_name, DETAIL_PAYMENT)
    old_in = _txn(db, item, card, "old-in", date(2034, 1, 1), -41, in_name, DETAIL_WAGES)
    db.add(TransferPair(txn_out_id=old_out.id, txn_in_id=old_in.id, detected_by="manual", confirmed=True))
    return old_out, old_in


def _new_pair(
    db, item, checking, card, *, key="new", out_name="AUTOPAY CARD REF 2002",
    in_name="CARD PAYMENT RECEIVED", out_detail=DETAIL_PAYMENT, in_detail=DETAIL_WAGES,
):
    out = _txn(db, item, checking, f"{key}-out", date(2034, 1, 12), 59, out_name, out_detail)
    inn = _txn(db, item, card, f"{key}-in", date(2034, 1, 10), -59, in_name, in_detail)
    return out, inn


def _seed_route_pair():
    db, item, checking, card, alternate = _setup()
    _history(db, item, checking, card)
    out, inn = _new_pair(db, item, checking, card)
    db.commit()
    return db, item, checking, card, alternate, out, inn


def _pair_for(db, out, inn):
    return db.query(TransferPair).filter_by(txn_out_id=out.id, txn_in_id=inn.id).one_or_none()


def test_confirmed_route_promotes_bounded_numeric_reference_variation():
    """One structured leg plus one stable historical leg is precise reusable evidence."""
    db, _, _, _, _, out, inn = _seed_route_pair()
    try:
        created = transfer_detector.detect_candidates(db)
        assert len(created) == 1
        pair = _pair_for(db, out, inn)
        assert pair is not None and pair.confirmed is True
        evidence = json.loads(pair.decision_evidence)
        assert evidence["kind"] == "confirmed_route_stable_leg"
        assert evidence["stable_leg"] == "in"
        assert evidence["variable_leg"] == "out"
    finally:
        db.close()


def test_redetection_promotes_a_preexisting_review_candidate():
    """Rebuilding review candidates must apply the same evidence decision."""
    db, _, _, _, _, out, inn = _seed_route_pair()
    try:
        db.add(TransferPair(txn_out_id=out.id, txn_in_id=inn.id, detected_by="auto", confirmed=False))
        db.commit()
        assert transfer_detector.clear_auto_pairs(db) == 1
        transfer_detector.detect_candidates(db)
        pair = _pair_for(db, out, inn)
        assert pair is not None and pair.confirmed is True
        assert pair.detected_by == "auto_confirmed"
    finally:
        db.close()


def test_successful_no_delta_refresh_rebuilds_and_promotes_review_candidate():
    """A successful refresh applies new reconciliation rules even with no rows added."""
    class NoDeltaClient:
        def get_accounts(self, _access_token):
            return [
                {
                    "account_id": "pi30-checking", "name": "Synthetic checking",
                    "official_name": None, "mask": None, "type": "depository",
                    "subtype": "checking", "current_balance": 0, "available_balance": 0,
                    "iso_currency_code": "USD", "limit": None,
                },
                {
                    "account_id": "pi30-card", "name": "Synthetic card",
                    "official_name": None, "mask": None, "type": "credit",
                    "subtype": "credit card", "current_balance": 0, "available_balance": 0,
                    "iso_currency_code": "USD", "limit": None,
                },
                {
                    "account_id": "pi30-alternate", "name": "Synthetic alternate",
                    "official_name": None, "mask": None, "type": "depository",
                    "subtype": "checking", "current_balance": 0, "available_balance": 0,
                    "iso_currency_code": "USD", "limit": None,
                },
            ]

        def sync_transactions(self, _access_token, _cursor):
            return {"added": [], "modified": [], "removed": [], "next_cursor": "pi30-no-delta"}

    db, item, _, _, _, out, inn = _seed_route_pair()
    try:
        db.add(TransferPair(txn_out_id=out.id, txn_in_id=inn.id, detected_by="auto", confirmed=False))
        db.commit()
        result = SyncService(NoDeltaClient()).sync_item(db, item.id)
        pair = _pair_for(db, out, inn)
        assert result["added"] == result["modified"] == result["removed"] == 0
        assert pair is not None and pair.confirmed is True
        assert pair.detected_by == "auto_confirmed"
    finally:
        db.close()


@pytest.mark.parametrize("reverse_insertion", [False, True])
def test_ambiguity_is_never_resolved_by_route_history_or_insertion_order(reverse_insertion):
    db, item, checking, card, alternate, out, inn = _seed_route_pair()
    try:
        rows = [
            (card, "competitor-in", date(2034, 1, 10), -59, "CARD PAYMENT RECEIVED", DETAIL_WAGES),
            (alternate, "competitor-out", date(2034, 1, 12), 59, "AUTOPAY CARD REF 2002", DETAIL_PAYMENT),
        ]
        for account, key, when, amount, name, detail in reversed(rows) if reverse_insertion else rows:
            _txn(db, item, account, key, when, amount, name, detail)
        db.commit()

        assert transfer_detector.detect_candidates(db) == []
        assert _pair_for(db, out, inn) is None
    finally:
        db.close()


@pytest.mark.parametrize(
    "old_out,new_out,old_in,new_in,out_detail,route_account",
    [
        # Both sides changing is not a stable route signature.
        ("AUTOPAY CARD REF 1001", "AUTOPAY CARD REF 2002", "CARD PAYMENT 3003", "CARD PAYMENT 4004", DETAIL_PAYMENT, "checking"),
        # A stable-leg wording change invalidates the historical evidence.
        ("AUTOPAY CARD REF 1001", "AUTOPAY CARD REF 2002", "CARD PAYMENT RECEIVED", "CARD PAYMENT SETTLED", DETAIL_PAYMENT, "checking"),
        # Digits must not erase a material payee/type change.
        ("AUTOPAY CARD REF 1001", "AUTOPAY LOAN REF 2002", "CARD PAYMENT RECEIVED", "CARD PAYMENT RECEIVED", DETAIL_PAYMENT, "checking"),
        # Neither provider leg corroborates a payment/transfer.
        ("AUTOPAY CARD REF 1001", "AUTOPAY CARD REF 2002", "CARD PAYMENT RECEIVED", "CARD PAYMENT RECEIVED", None, "checking"),
        # An account reference is not the explicit bounded route reference.
        ("AUTOPAY CARD ACCOUNT 1001", "AUTOPAY CARD ACCOUNT 2002", "CARD PAYMENT RECEIVED", "CARD PAYMENT RECEIVED", DETAIL_PAYMENT, "checking"),
        # A date-shaped token is not a bounded route reference.
        ("AUTOPAY CARD REF 20340101", "AUTOPAY CARD REF 20340102", "CARD PAYMENT RECEIVED", "CARD PAYMENT RECEIVED", DETAIL_PAYMENT, "checking"),
        # Arbitrary numeric wording must never become a trusted signature.
        ("PAYMENT NOTICE 1001", "PAYMENT NOTICE 2002", "CARD PAYMENT RECEIVED", "CARD PAYMENT RECEIVED", DETAIL_PAYMENT, "checking"),
        # History on one directed account route cannot bless another route.
        ("AUTOPAY CARD REF 1001", "AUTOPAY CARD REF 2002", "CARD PAYMENT RECEIVED", "CARD PAYMENT RECEIVED", DETAIL_PAYMENT, "alternate"),
    ],
)
def test_route_history_abstains_outside_the_narrow_variable_reference_shape(
    old_out, new_out, old_in, new_in, out_detail, route_account
):
    db, item, checking, card, alternate = _setup()
    try:
        _history(db, item, checking, card, out_name=old_out, in_name=old_in)
        route = checking if route_account == "checking" else alternate
        out, inn = _new_pair(
            db, item, route, card, out_name=new_out, in_name=new_in,
            out_detail=out_detail, in_detail=DETAIL_WAGES,
        )
        db.commit()
        transfer_detector.detect_candidates(db)
        pair = _pair_for(db, out, inn)
        assert pair is not None and pair.confirmed is False
    finally:
        db.close()


def test_rejected_and_manual_pairs_are_not_replaced_by_variable_route_redetection():
    db, _, _, _, _, out, inn = _seed_route_pair()
    try:
        transfer_detector.reject_pair(db, out.id, inn.id)
        db.commit()
        assert transfer_detector.detect_candidates(db) == []

        transfer_detector.unreject_pair(db, out.id, inn.id)
        manual = transfer_detector.manual_pair(db, out.id, inn.id)
        assert manual.detected_by == "manual" and manual.confirmed is True
        assert transfer_detector.clear_auto_pairs(db) == 0
        assert transfer_detector.detect_candidates(db) == []
        assert _pair_for(db, out, inn).id == manual.id
    finally:
        db.close()


def test_source_change_reopens_an_auto_confirmed_variable_route_pair():
    db, _, _, _, _, out, inn = _seed_route_pair()
    try:
        transfer_detector.detect_candidates(db)
        pair = _pair_for(db, out, inn)
        assert pair is not None and pair.confirmed is True
        inn.name = "CARD CREDIT RECEIVED"
        db.commit()
        assert transfer_detector.revalidate_auto_confirmed_pairs(db) == 1
        assert _pair_for(db, out, inn) is None
    finally:
        db.close()


def test_only_the_strong_route_is_excluded_from_activity_and_sankey():
    db, item, checking, card, _, strong_out, strong_in = _seed_route_pair()
    try:
        weak_out = _txn(db, item, checking, "weak-out", date(2034, 1, 22), 59,
                        "AUTOPAY CARD REF 3003", None)
        weak_in = _txn(db, item, card, "weak-in", date(2034, 1, 20), -59,
                       "CARD PAYMENT RECEIVED", DETAIL_WAGES)
        db.commit()
        transfer_detector.detect_candidates(db)
        strong_out_id, strong_in_id = strong_out.id, strong_in.id
        weak_out_id, weak_in_id = weak_out.id, weak_in.id
    finally:
        db.close()

    with TestClient(app) as client:
        activity = client.get("/transactions", params=BOUNDS, headers=AUTH_HEADERS).json()["items"]
        sankey = client.get("/analytics/cashflow-sankey", params=BOUNDS, headers=AUTH_HEADERS).json()

    rows = {row["id"]: row for row in activity}
    assert rows[strong_out_id]["is_transfer"] is True
    assert rows[strong_in_id]["is_transfer"] is True
    assert rows[weak_out_id]["is_transfer"] is False
    assert rows[weak_in_id]["is_transfer"] is False
    assert rows[weak_out_id]["is_transfer_candidate"] is True
    assert sankey["total_spend"] == 59.0
