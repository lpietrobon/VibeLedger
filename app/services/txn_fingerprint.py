import hashlib
from datetime import date
from decimal import Decimal


def compute_txn_hash(account_mask: str | None, txn_date: date, amount: Decimal, name: str) -> str:
    """Content-based fingerprint, stable across re-syncs of the same underlying bank data.

    Uses fields that come back identically when the same historical transaction
    is re-pulled from the bank after an item is removed and re-linked.
    """
    raw = f"{account_mask or ''}|{txn_date.isoformat()}|{Decimal(amount):.2f}|{name}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
