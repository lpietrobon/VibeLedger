"""Durable manual duplicate corrections and their lifecycle rules."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.models import (
    Account,
    DuplicateCorrection,
    Transaction,
    TransactionAnnotation,
    TransferPair,
)


ACTIVE = "active"
REVERSED = "reversed"
INVALIDATED = "invalidated"


def _currency(txn: Transaction, account: Account) -> str | None:
    """Return only trustworthy reporting currency evidence."""
    value = None
    if txn.raw_json:
        try:
            raw = json.loads(txn.raw_json)
        except (TypeError, ValueError):
            return None
        value = raw.get("iso_currency_code")
        unofficial = raw.get("unofficial_currency_code")
        if unofficial:
            return None
    value = value or account.currency
    if not value or not str(value).strip():
        return None
    return str(value).strip().upper()


def _snapshot(txn: Transaction, account: Account) -> dict:
    return {
        "plaid_transaction_id": txn.plaid_transaction_id,
        "txn_hash": txn.txn_hash,
        "txn_occurrence": txn.txn_occurrence,
        "account_plaid_id": account.plaid_account_id,
        "date": txn.date.isoformat(),
        "amount": str(txn.amount),
        "name": txn.name,
        "currency": _currency(txn, account),
    }


def _matches_snapshot(txn: Transaction, account: Account, snapshot: dict) -> bool:
    """Require the relinked source to still be the recorded source evidence."""
    try:
        return (
            txn.plaid_transaction_id == snapshot.get("plaid_transaction_id")
            and txn.date.isoformat() == snapshot.get("date")
            and Decimal(str(txn.amount)) == Decimal(str(snapshot.get("amount")))
            and account.plaid_account_id == snapshot.get("account_plaid_id")
            and _currency(txn, account) == snapshot.get("currency")
        )
    except (TypeError, ValueError):
        return False


def _active_endpoint_ids(db: Session, txn_id: int) -> bool:
    return db.query(DuplicateCorrection.id).filter(
        DuplicateCorrection.status == ACTIVE,
        or_(
            DuplicateCorrection.canonical_transaction_id == txn_id,
            DuplicateCorrection.duplicate_transaction_id == txn_id,
        ),
    ).first() is not None


def validate_pair(db: Session, canonical_id: int, duplicate_id: int) -> tuple[Transaction, Transaction, Account, Account]:
    if canonical_id == duplicate_id:
        raise HTTPException(status_code=400, detail="duplicate correction requires two distinct transactions")
    canonical = db.get(Transaction, canonical_id)
    duplicate = db.get(Transaction, duplicate_id)
    if not canonical or not duplicate:
        raise HTTPException(status_code=400, detail="both transactions must exist")
    if canonical.pending or duplicate.pending:
        raise HTTPException(status_code=400, detail="pending transactions must be posted before correction")

    canonical_account = db.get(Account, canonical.account_id)
    duplicate_account = db.get(Account, duplicate.account_id)
    if not canonical_account or not duplicate_account or canonical.account_id != duplicate.account_id:
        raise HTTPException(status_code=400, detail="transactions must belong to the same account")
    canonical_currency = _currency(canonical, canonical_account)
    duplicate_currency = _currency(duplicate, duplicate_account)
    if (
        not canonical_currency
        or not duplicate_currency
        or canonical_currency != duplicate_currency
        or canonical_currency != "USD"
    ):
        raise HTTPException(
            status_code=400,
            detail="transactions must have the same supported reporting currency (USD)",
        )
    if canonical.amount != duplicate.amount:
        raise HTTPException(status_code=400, detail="transactions must have the same signed amount")
    if _active_endpoint_ids(db, canonical.id) or _active_endpoint_ids(db, duplicate.id):
        raise HTTPException(status_code=400, detail="a transaction already belongs to an active duplicate correction")
    if db.query(TransferPair.id).filter(
        or_(TransferPair.txn_out_id.in_([canonical.id, duplicate.id]), TransferPair.txn_in_id.in_([canonical.id, duplicate.id]))
    ).first() is not None:
        raise HTTPException(status_code=400, detail="transfer-related transactions must be resolved first")

    annotations = db.query(TransactionAnnotation).filter(
        or_(
            TransactionAnnotation.transaction_id.in_([canonical.id, duplicate.id]),
            TransactionAnnotation.refund_match_transaction_id.in_([canonical.id, duplicate.id]),
        )
    ).all()
    if any(a.refund_status in {"confirmed", "likely"} for a in annotations):
        raise HTTPException(status_code=400, detail="refund-related transactions must be resolved first")
    return canonical, duplicate, canonical_account, duplicate_account


def create_correction(db: Session, canonical_id: int, duplicate_id: int) -> DuplicateCorrection:
    canonical, duplicate, canonical_account, duplicate_account = validate_pair(db, canonical_id, duplicate_id)
    correction = DuplicateCorrection(
        canonical_transaction_id=canonical.id,
        duplicate_transaction_id=duplicate.id,
        status=ACTIVE,
        evidence_json=json.dumps({
            "canonical": _snapshot(canonical, canonical_account),
            "duplicate": _snapshot(duplicate, duplicate_account),
        }, sort_keys=True),
    )
    db.add(correction)
    db.flush()
    return correction


def mark_invalidated(db: Session, txn_id: int, reason: str) -> None:
    db.query(DuplicateCorrection).filter(
        DuplicateCorrection.status == ACTIVE,
        or_(
            DuplicateCorrection.canonical_transaction_id == txn_id,
            DuplicateCorrection.duplicate_transaction_id == txn_id,
        ),
    ).update({
        DuplicateCorrection.status: INVALIDATED,
        DuplicateCorrection.invalidation_reason: reason,
    }, synchronize_session=False)


def invalidate_missing_endpoints(db: Session) -> None:
    """Invalidate active records whose endpoint was deleted outside the ORM."""
    db.query(DuplicateCorrection).filter(
        DuplicateCorrection.status == ACTIVE,
        or_(
            ~DuplicateCorrection.canonical_transaction_id.in_(db.query(Transaction.id)),
            ~DuplicateCorrection.duplicate_transaction_id.in_(db.query(Transaction.id)),
        ),
    ).update({
        DuplicateCorrection.status: INVALIDATED,
        DuplicateCorrection.invalidation_reason: "source transaction removed",
    }, synchronize_session=False)


def reapply_relinked(db: Session) -> None:
    """Reattach invalidated corrections only when provider identities are unique."""
    rows = db.query(DuplicateCorrection).filter(DuplicateCorrection.status == INVALIDATED).all()
    for correction in rows:
        try:
            evidence = json.loads(correction.evidence_json or "{}")
            matches = []
            for side in ("canonical", "duplicate"):
                provider_id = evidence.get(side, {}).get("plaid_transaction_id")
                candidates = db.query(Transaction).filter(Transaction.plaid_transaction_id == provider_id).all()
                if len(candidates) != 1:
                    raise ValueError
                candidate = candidates[0]
                account = db.get(Account, candidate.account_id)
                if not account or not _matches_snapshot(candidate, account, evidence.get(side, {})):
                    raise ValueError
                matches.append(candidate)
            canonical, duplicate, _, _ = validate_pair(db, matches[0].id, matches[1].id)
            correction.canonical_transaction_id = canonical.id
            correction.duplicate_transaction_id = duplicate.id
            correction.status = ACTIVE
            correction.invalidation_reason = None
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, HTTPException):
            continue


def response(correction: DuplicateCorrection) -> dict:
    return {
        "id": correction.id,
        "canonical_transaction_id": correction.canonical_transaction_id,
        "duplicate_transaction_id": correction.duplicate_transaction_id,
        "status": correction.status,
    }
