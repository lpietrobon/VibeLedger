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
  * exactly one best candidate — ties are left unpaired for manual review

Plaid sign convention: positive = money leaving the account.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.models import Account, RejectedTransferPair, Transaction, TransferPair


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


def detect_candidates(db: Session, window_days: int = 3) -> list[TransferPair]:
    """Pair outflows with their counterparty inflow. Returns new TransferPairs.

    Idempotent: already-paired transactions are skipped.
    """
    paired = _paired_ids(db)
    rejected = _rejected_pairs(db)

    # Pending rows are transient and their amounts can still change.
    txns = (
        db.query(Transaction)
        .filter(Transaction.pending == False)  # noqa: E712
        .order_by(Transaction.date.asc(), Transaction.id.asc())
        .all()
    )

    # Index inflows by absolute amount so matching is a lookup rather than a
    # full scan per outflow (this used to be O(n^2) over the whole ledger).
    inflows_by_amount: dict[Decimal, list[Transaction]] = defaultdict(list)
    for t in txns:
        if t.amount is not None and t.amount < 0:
            inflows_by_amount[-t.amount].append(t)

    created: list[TransferPair] = []

    for out_txn in txns:
        if out_txn.id in paired or out_txn.amount is None or out_txn.amount <= 0:
            continue

        candidates: list[tuple[int, Transaction]] = []
        for in_txn in inflows_by_amount.get(out_txn.amount, ()):
            if in_txn.id in paired or in_txn.account_id == out_txn.account_id:
                continue
            if (out_txn.id, in_txn.id) in rejected:
                continue  # the user already said these two are not a transfer
            # Direction matters: money leaves before (or the same day as) it
            # arrives. Allowing the inflow to precede the outflow would double
            # the window in which unrelated amounts can collide.
            gap = (in_txn.date - out_txn.date).days
            if gap < 0 or gap > window_days:
                continue
            candidates.append((gap, in_txn))

        if not candidates:
            continue

        best_gap = min(gap for gap, _ in candidates)
        tied = [txn for gap, txn in candidates if gap == best_gap]
        if len(tied) > 1:
            # Two equally-plausible counterparties: guessing would be a coin
            # flip that silently moves money out of the analytics, so leave both
            # unpaired and let the review queue surface them.
            continue

        match = tied[0]
        pair = TransferPair(
            txn_out_id=out_txn.id,
            txn_in_id=match.id,
            detected_by="auto",
            confirmed=False,
        )
        db.add(pair)
        paired.add(out_txn.id)
        paired.add(match.id)
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
    if not a or not b:
        raise ValueError("transaction not found")
    if a.account_id == b.account_id:
        raise ValueError("transfer pair must span two accounts")
    if a.amount + b.amount != 0:
        raise ValueError("transfer pair amounts must be opposite and equal")

    paired = _paired_ids(db)
    if a.id in paired or b.id in paired:
        raise ValueError("one or both transactions already paired")

    unreject_pair(db, a.id, b.id)

    if a.amount > 0:
        out_id, in_id = a.id, b.id
    else:
        out_id, in_id = b.id, a.id

    pair = TransferPair(
        txn_out_id=out_id,
        txn_in_id=in_id,
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
    if not out or not inn:
        raise ValueError("transfer pair transaction no longer exists")
    if out.pending or inn.pending:
        raise ValueError("pending transactions cannot form a confirmed transfer")
    if out.account_id == inn.account_id:
        raise ValueError("transfer pair must span two accounts")
    if out.amount <= 0 or inn.amount >= 0 or out.amount + inn.amount != 0:
        raise ValueError("transfer pair amounts must be opposite and equal")

    out_account = db.get(Account, out.account_id)
    in_account = db.get(Account, inn.account_id)
    if out_account and in_account and out_account.currency and in_account.currency:
        if out_account.currency != in_account.currency:
            raise ValueError("transfer pair currencies must match")

    pair.confirmed = True
    db.commit()
    db.refresh(pair)
    return pair


def transfer_txn_ids(db: Session) -> set[int]:
    """All transaction ids that are part of a transfer pair (either side)."""
    return _paired_ids(db)
