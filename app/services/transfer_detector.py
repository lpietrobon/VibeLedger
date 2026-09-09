"""Detection of internal transfers — money moving between two covered accounts.

A transfer is *defined* as a matched pair of transactions across two accounts
linked in this app. If a movement has no counterparty in scope it is simply not
a transfer here: paying a credit card from an unlinked checking account leaves a
single unpaired transaction, and that is the correct outcome, not a one-sided
"transfer".

The point of pairing is to stop the same money being counted as both income and
expense. Analytics exclude paired transactions for exactly that reason, so a
wrong pair silently distorts the numbers — the matching rules below are
deliberately conservative and refuse to guess.

Matching rule (all required):
  * equal absolute amount, opposite signs
  * two different covered accounts
  * the outflow lands on or before the inflow, within `window_days`
  * both account currencies are known and equal
  * each side has exactly one closest candidate — ties are left unpaired for
    manual review

Plaid sign convention: positive = money leaving the account.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.models import (
    Account,
    RejectedTransferPair,
    Transaction,
    TransactionAnnotation,
    TransferPair,
)
from app.services.category_resolver import detailed_category
from app.services.duplicate_corrections import active_duplicate_ids


MAX_POSTING_GAP_DAYS = 14
# Card issuers can post the credit to the card before the funding account's
# outflow.  Keep this exception deliberately narrower than the manual-pair
# validation window and the generic detector window: PI-06 observed gaps of up
# to four days, while unrelated reverse-order equal amounts remain invalid.
CARD_PAYMENT_REVERSE_GAP_DAYS = 4
CARD_PAYMENT_CATEGORY = "FINANCE/CREDIT_CARD_PAYMENT"
_PAYMENT_WORD = re.compile(r"\bpayment\b|\bautopay\b", re.IGNORECASE)


def _is_checking(account: Account | None) -> bool:
    return bool(
        account
        and (account.type or "").lower() == "depository"
        and (account.subtype or "").lower().replace("_", " ") == "checking"
    )


def _is_credit_card(account: Account | None) -> bool:
    return bool(
        account
        and (account.type or "").lower() == "credit"
        and (account.subtype or "").lower().replace("_", " ") == "credit card"
    )


def _explicit_category(txn: Transaction, annotation: TransactionAnnotation | None) -> str | None:
    if annotation and annotation.user_category:
        return annotation.user_category
    if annotation and annotation.rule_category:
        return annotation.rule_category
    return None


def _provider_card_payment_detail(txn: Transaction) -> bool:
    """Recognize Plaid's explicit credit-card-payment detail, if present."""
    try:
        raw = json.loads(txn.raw_json or "{}")
    except (TypeError, ValueError):
        return False
    if not isinstance(raw, dict):
        return False
    category = raw.get("personal_finance_category") or {}
    if not isinstance(category, dict):
        return False
    detail = category.get("detailed") or ""
    if not isinstance(detail, str):
        return False
    detail = detail.upper()
    return "CREDIT_CARD" in detail and "PAYMENT" in detail


def _has_payment_evidence(txn: Transaction, annotation: TransactionAnnotation | None) -> bool:
    """Require explicit payment evidence on each leg of the card exception.

    An exact user/rule category or provider detailed category is strongest.  A
    provider description containing payment/autopay is retained as evidence for
    issuers whose category detail is absent, as documented by PI-06.
    """
    category = (_explicit_category(txn, annotation) or "").upper()
    if category == CARD_PAYMENT_CATEGORY:
        return True
    if _provider_card_payment_detail(txn):
        return True
    return bool(_PAYMENT_WORD.search(txn.name or "") or _PAYMENT_WORD.search(txn.merchant_name or ""))


def _is_evidence_qualified_card_repayment(
    db: Session,
    out: Transaction,
    inn: Transaction,
) -> bool:
    """Return true only for a checking outflow ↔ credit-card payment credit."""
    out_account = db.get(Account, out.account_id)
    in_account = db.get(Account, inn.account_id)
    # The exception is specifically for a checking-account repayment whose
    # receipt was posted on the credit-card side first.  A reverse credit-card
    # outflow to checking is a different movement and must retain the generic
    # posting-order guard.
    if not (_is_checking(out_account) and _is_credit_card(in_account)):
        return False

    annotations = {
        row.transaction_id: row
        for row in db.query(TransactionAnnotation).filter(
            TransactionAnnotation.transaction_id.in_([out.id, inn.id])
        ).all()
    }
    return _has_payment_evidence(out, annotations.get(out.id)) and _has_payment_evidence(
        inn, annotations.get(inn.id)
    )


def _paired_ids(db: Session) -> set[int]:
    rows = db.execute(select(TransferPair.txn_out_id, TransferPair.txn_in_id)).all()
    out: set[int] = set()
    for a, b in rows:
        out.add(a)
        out.add(b)
    return out


def _rejected_pairs(db: Session) -> set[tuple[int, int]]:
    """Combinations the user has explicitly unpaired."""
    rows = db.execute(
        select(RejectedTransferPair.txn_out_id, RejectedTransferPair.txn_in_id)
    ).all()
    return {(a, b) for a, b in rows}


def reject_pair(db: Session, txn_out_id: int, txn_in_id: int) -> None:
    """Remember that these two transactions are not a transfer.

    Detection is re-run after every sync, so without this an unpaired
    false positive simply comes back.
    """
    exists = (
        db.query(RejectedTransferPair)
        .filter(
            RejectedTransferPair.txn_out_id == txn_out_id,
            RejectedTransferPair.txn_in_id == txn_in_id,
        )
        .first()
    )
    if not exists:
        db.add(RejectedTransferPair(txn_out_id=txn_out_id, txn_in_id=txn_in_id))


def unreject_pair(db: Session, txn_a_id: int, txn_b_id: int) -> None:
    """Forget a rejection, in either direction (used when manually pairing)."""
    db.query(RejectedTransferPair).filter(
        or_(
            and_(
                RejectedTransferPair.txn_out_id == txn_a_id,
                RejectedTransferPair.txn_in_id == txn_b_id,
            ),
            and_(
                RejectedTransferPair.txn_out_id == txn_b_id,
                RejectedTransferPair.txn_in_id == txn_a_id,
            ),
        )
    ).delete(synchronize_session=False)


def validate_pair(
    db: Session,
    txn_a: Transaction | None,
    txn_b: Transaction | None,
    *,
    max_gap_days: int = MAX_POSTING_GAP_DAYS,
) -> tuple[Transaction, Transaction]:
    """Validate source evidence and return it in outflow/inflow order.

    A confirmation is an accounting decision, so automatic detection and manual
    pairing intentionally share the same strict evidence boundary.  Unknown
    currency is not assumed to be USD (or to match another unknown currency).
    """
    if not txn_a or not txn_b:
        raise ValueError("transaction not found")
    if txn_a.id == txn_b.id:
        raise ValueError("transfer pair must use two different transactions")
    if txn_a.pending or txn_b.pending:
        raise ValueError("pending transactions cannot form a transfer pair")
    if txn_a.amount is None or txn_b.amount is None:
        raise ValueError("transfer pair amounts are required")
    if txn_a.amount > 0 and txn_b.amount < 0:
        out, inn = txn_a, txn_b
    elif txn_b.amount > 0 and txn_a.amount < 0:
        out, inn = txn_b, txn_a
    else:
        raise ValueError("transfer pair amounts must be nonzero, opposite, and equal")
    if out.amount + inn.amount != 0:
        raise ValueError("transfer pair amounts must be opposite and equal")
    if out.account_id == inn.account_id:
        raise ValueError("transfer pair must span two accounts")

    gap = (inn.date - out.date).days
    if gap < 0:
        if not _is_evidence_qualified_card_repayment(db, out, inn):
            raise ValueError("transfer outflow must post on or before its inflow")
        if abs(gap) > CARD_PAYMENT_REVERSE_GAP_DAYS:
            raise ValueError(
                f"card payment posting dates must be within {CARD_PAYMENT_REVERSE_GAP_DAYS} days"
            )
    elif gap > max_gap_days:
        raise ValueError(f"transfer posting dates must be within {max_gap_days} days")

    out_account = db.get(Account, out.account_id)
    in_account = db.get(Account, inn.account_id)
    out_currency = (out_account.currency or "").upper() if out_account else ""
    in_currency = (in_account.currency or "").upper() if in_account else ""
    if not out_currency or not in_currency:
        raise ValueError("transfer pair currencies must be known and match")
    if out_currency != in_currency:
        raise ValueError("transfer pair currencies must match")
    return out, inn


def _sole_closest(candidates: list[tuple[int, Transaction]]) -> Transaction | None:
    """Return the sole closest counterparty, or None when it is ambiguous."""
    if not candidates:
        return None
    best_gap = min(gap for gap, _ in candidates)
    closest = [txn for gap, txn in candidates if gap == best_gap]
    return closest[0] if len(closest) == 1 else None


def detect_candidates(db: Session, window_days: int = 3) -> list[TransferPair]:
    """Pair outflows with their counterparty inflow. Returns new TransferPairs.

    Idempotent: already-paired transactions are skipped.
    """
    paired = _paired_ids(db)
    rejected = _rejected_pairs(db)

    # Pending rows are transient and their amounts can still change.
    active_duplicates = active_duplicate_ids(db)
    txns = (
        db.query(Transaction)
        .filter(Transaction.pending == False)  # noqa: E712
        .order_by(Transaction.date.asc(), Transaction.id.asc())
        .all()
    )
    txns = [txn for txn in txns if txn.id not in active_duplicates]

    # Index inflows by absolute amount so matching is a lookup rather than a
    # full scan per outflow (this used to be O(n^2) over the whole ledger).
    inflows_by_amount: dict[Decimal, list[Transaction]] = defaultdict(list)
    for t in txns:
        if t.amount is not None and t.amount < 0:
            inflows_by_amount[-t.amount].append(t)

    candidates_by_out: dict[int, list[tuple[int, Transaction]]] = defaultdict(list)
    candidates_by_in: dict[int, list[tuple[int, Transaction]]] = defaultdict(list)
    for out_txn in txns:
        if out_txn.id in paired or out_txn.amount is None or out_txn.amount <= 0:
            continue
        for in_txn in inflows_by_amount.get(out_txn.amount, ()):
            if in_txn.id in paired or in_txn.account_id == out_txn.account_id:
                continue
            if (out_txn.id, in_txn.id) in rejected:
                continue  # the user already said these two are not a transfer
            try:
                out, inn = validate_pair(db, out_txn, in_txn, max_gap_days=window_days)
            except ValueError:
                continue
            # Forward pairs have a non-negative gap; the card-payment exception
            # can be reverse ordered, so rank all candidates by elapsed days.
            gap = abs((inn.date - out.date).days)
            candidates_by_out[out.id].append((gap, inn))
            candidates_by_in[inn.id].append((gap, out))

    best_in_by_out = {
        out_id: _sole_closest(candidates)
        for out_id, candidates in candidates_by_out.items()
    }
    best_out_by_in = {
        in_id: _sole_closest(candidates)
        for in_id, candidates in candidates_by_in.items()
    }

    created: list[TransferPair] = []
    for out_txn in txns:
        match = best_in_by_out.get(out_txn.id)
        if not match or best_out_by_in.get(match.id) is not out_txn:
            # A one-sided winner is still ambiguous: another same-size outflow
            # may be the inbound leg's equally plausible (or closer) match.
            continue
        pair = TransferPair(
            txn_out_id=out_txn.id,
            txn_in_id=match.id,
            detected_by="auto",
            confirmed=False,
        )
        db.add(pair)
        created.append(pair)

    if created:
        db.commit()
        for p in created:
            db.refresh(p)
    return created


def clear_auto_pairs(db: Session) -> int:
    """Delete unconfirmed auto-detected pairs. Confirmed and manual pairs stay.

    Lets a re-detect discard stale guesses (e.g. after the matching rules change
    or a new account is linked) without touching anything the user has vetted.
    """
    deleted = (
        db.query(TransferPair)
        .filter(TransferPair.detected_by == "auto", TransferPair.confirmed == False)  # noqa: E712
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(deleted or 0)


def manual_pair(db: Session, txn_a_id: int, txn_b_id: int) -> TransferPair:
    a = db.get(Transaction, txn_a_id)
    b = db.get(Transaction, txn_b_id)
    out, inn = validate_pair(db, a, b)

    paired = _paired_ids(db)
    if out.id in paired or inn.id in paired:
        raise ValueError("one or both transactions already paired")

    unreject_pair(db, out.id, inn.id)

    pair = TransferPair(
        txn_out_id=out.id,
        txn_in_id=inn.id,
        detected_by="manual",
        confirmed=True,
    )
    db.add(pair)
    db.commit()
    db.refresh(pair)
    return pair


def confirm_pair(db: Session, pair: TransferPair) -> TransferPair:
    """Confirm an existing candidate only while its source evidence is valid."""
    out = db.get(Transaction, pair.txn_out_id)
    inn = db.get(Transaction, pair.txn_in_id)
    validate_pair(db, out, inn)

    pair.confirmed = True
    db.commit()
    db.refresh(pair)
    return pair


def transfer_txn_ids(db: Session) -> set[int]:
    """All transaction ids that are part of a transfer pair (either side)."""
    return _paired_ids(db)
