"""Heuristic transfer-pair detection.

Pairs an outflow (amount > 0, positive = money leaving per Plaid sign convention)
with an opposite inflow on a different account within a small date window.
Idempotent — already-paired transactions are skipped.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.models import Transaction, TransferPair


def _paired_ids(db: Session) -> set[int]:
    rows = db.execute(select(TransferPair.txn_out_id, TransferPair.txn_in_id)).all()
    out: set[int] = set()
    for a, b in rows:
        out.add(a)
        out.add(b)
    return out


def detect_candidates(db: Session, window_days: int = 3) -> list[TransferPair]:
    """Greedy nearest-date pairing. Returns newly created TransferPair rows."""
    paired = _paired_ids(db)

    # Only consider non-pending to avoid matching a transient row.
    txns = (
        db.query(Transaction)
        .filter(Transaction.pending == False)  # noqa: E712
        .order_by(Transaction.date.asc(), Transaction.id.asc())
        .all()
    )

    by_id = {t.id: t for t in txns}
    created: list[TransferPair] = []

    for t in txns:
        if t.id in paired or t.amount is None or t.amount <= 0:
            continue

        best: Transaction | None = None
        best_gap: int | None = None
        for u in txns:
            if u.id == t.id or u.id in paired:
                continue
            if u.account_id == t.account_id:
                continue
            if u.amount is None or u.amount >= 0:
                continue
            if u.amount != -t.amount:
                continue
            gap = abs((u.date - t.date).days)
            if gap > window_days:
                continue
            if best is None or gap < best_gap:
                best = u
                best_gap = gap

        if best is not None:
            pair = TransferPair(
                txn_out_id=t.id,
                txn_in_id=best.id,
                detected_by="auto",
                confirmed=False,
            )
            db.add(pair)
            paired.add(t.id)
            paired.add(best.id)
            created.append(pair)

    if created:
        db.commit()
        for p in created:
            db.refresh(p)
    return created


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


def transfer_txn_ids(db: Session) -> set[int]:
    """All transaction ids that are part of a transfer pair (either side)."""
    return _paired_ids(db)
