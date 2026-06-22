"""High-confidence refund classification.

Plaid's sign convention makes refunds negative, but negative transactions also
include income and transfers. This detector only marks a transaction as likely
when it has an exact earlier charge match on the same account.
"""
from __future__ import annotations

import json
import re
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.models import Transaction, TransactionAnnotation, TransferPair
from app.services.category_resolver import detailed_category, friendly_category


_NON_REFUND_ROOTS = {"INCOME", "TRANSFER", "FINANCE"}


def _normalized(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _effective_category(tx: Transaction, annotation: TransactionAnnotation | None) -> str:
    if annotation and annotation.user_category:
        return annotation.user_category
    if annotation and annotation.rule_category:
        return annotation.rule_category
    return friendly_category(
        tx.plaid_category_primary,
        detailed_category(tx.raw_json),
    ) or "uncategorized"


def _plaid_refund_code(tx: Transaction) -> bool:
    try:
        return json.loads(tx.raw_json or "{}").get("transaction_code") == "refund"
    except (TypeError, ValueError):
        return False


def classify_refunds(db: Session, lookback_days: int = 540) -> dict:
    """Recompute automatic refund classifications without overriding decisions."""
    annotations = {
        a.transaction_id: a
        for a in db.query(TransactionAnnotation).all()
    }
    paired_ids = {
        tx_id
        for pair in db.query(TransferPair).all()
        for tx_id in (pair.txn_out_id, pair.txn_in_id)
    }

    for annotation in annotations.values():
        if annotation.refund_status == "likely":
            annotation.refund_status = None
            annotation.refund_match_transaction_id = None
            annotation.refund_reason = None

    transactions = (
        db.query(Transaction)
        .filter(Transaction.pending == False)  # noqa: E712
        .order_by(Transaction.date.asc(), Transaction.id.asc())
        .all()
    )
    charges = [tx for tx in transactions if tx.amount is not None and tx.amount > 0]
    likely_count = 0
    confirmed_count = 0

    for tx in transactions:
        if tx.amount is None or tx.amount >= 0 or tx.id in paired_ids:
            continue

        annotation = annotations.get(tx.id)
        if annotation and annotation.refund_status in {"confirmed", "not_refund"}:
            continue
        if annotation and annotation.is_transfer_override:
            continue

        if _plaid_refund_code(tx):
            if annotation is None:
                annotation = TransactionAnnotation(transaction_id=tx.id)
                db.add(annotation)
                annotations[tx.id] = annotation
            annotation.refund_status = "confirmed"
            annotation.refund_reason = "Plaid transaction_code=refund"
            confirmed_count += 1
            continue

        category_root = _effective_category(tx, annotation).split("/", 1)[0].upper()
        if category_root in _NON_REFUND_ROOTS:
            continue

        if annotation is None:
            annotation = TransactionAnnotation(transaction_id=tx.id)
            db.add(annotation)
            annotations[tx.id] = annotation

        tx_name = _normalized(tx.name)
        candidates = [
            charge
            for charge in charges
            if charge.account_id == tx.account_id
            and charge.date <= tx.date
            and tx.date - charge.date <= timedelta(days=lookback_days)
            and charge.amount == -tx.amount
            and _normalized(charge.name) == tx_name
        ]
        if not candidates:
            continue

        match = max(candidates, key=lambda charge: (charge.date, charge.id))
        annotation.refund_status = "likely"
        annotation.refund_match_transaction_id = match.id
        annotation.refund_reason = "Exact account, amount, and transaction-name match"
        likely_count += 1

    db.commit()
    return {"likely": likely_count, "confirmed": confirmed_count}
