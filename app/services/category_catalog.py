"""The category vocabulary offered by pickers.

Merges three sources into one list:
  * ledger    — categories transactions actually resolve to right now (with counts)
  * rule      — targets of category rules, even if nothing matches them yet
  * default   — a curated starter taxonomy so a fresh DB is never empty

Kept pure (no DB access) so the merge is unit testable; the API layer supplies
the rows. See docs/ for the picker spec.

`PARENT/CHILD` is a convention, not an invariant: 1-level values are common
(unmapped Plaid primaries pass straight through) and deeper values are legal.
Nothing here assumes a depth.
"""
from __future__ import annotations

import re

#: Curated starter taxonomy. Lives here rather than in the frontend so every
#: client (React, Streamlit) offers the same baseline. Every value targeted by
#: PLAID_FRIENDLY_MAP / PLAID_DETAILED_FRIENDLY_MAP must appear here — there is a
#: test asserting exactly that, so the two stay in step.
DEFAULT_CATEGORIES: list[str] = [
    "HOUSING", "HOUSING/RENT_AND_UTILITIES", "HOUSING/UTILITIES",
    "FOOD", "FOOD/GROCERIES", "FOOD/DINING", "FOOD/COFFEE", "FOOD/OTHER",
    "TRANSPORT", "TRANSPORT/RIDESHARE", "TRANSPORT/FUEL", "TRANSPORT/PARKING",
    "TRANSPORT/OTHER",
    "SHOPPING", "SHOPPING/GENERAL", "SHOPPING/CLOTHING", "SHOPPING/HOME",
    "SHOPPING/ELECTRONICS",
    "FUN", "FUN/ENTERTAINMENT", "FUN/TRAVEL", "FUN/EVENTS",
    "HEALTH", "HEALTH/MEDICAL", "HEALTH/PERSONAL_CARE", "HEALTH/FITNESS",
    "FINANCE", "FINANCE/LOANS", "FINANCE/FEES", "FINANCE/INVESTING",
    "INCOME", "INCOME/SALARY", "INCOME/INTEREST", "INCOME/REFUND", "INCOME/OTHER",
    "SERVICES/GENERAL", "SUBSCRIPTIONS", "UNCATEGORIZED",
]

#: Precedence when the same category arrives from more than one source.
_SOURCE_RANK = {"ledger": 0, "rule": 1, "default": 2}


def normalize_category(value: str | None) -> str:
    """Canonical form of a category token.

    Mirrors normalizeCategory() in the React picker exactly: trim, spaces to
    underscores, collapse repeated slashes, uppercase.
    """
    if not value:
        return ""
    collapsed = re.sub(r"\s+", "_", value.strip())
    return re.sub(r"/+", "/", collapsed).upper()


def merge_catalog(
    ledger_rows: list[tuple[str, int]],
    rule_categories: list[str] | None = None,
    defaults: list[str] | None = None,
) -> list[dict]:
    """Merge the three sources, deduping case-insensitively.

    Counts are summed across case variants — this is what collapses the SQL
    fallback literal 'uncategorized' and a manual "UNCATEGORIZED" annotation
    into a single row. Sorted by count desc, then value, so output is stable.
    """
    merged: dict[str, dict] = {}

    def add(raw: str | None, count: int, source: str) -> None:
        key = normalize_category(raw)
        if not key:
            return
        existing = merged.get(key)
        if existing is None:
            merged[key] = {"value": key, "count": count, "source": source}
            return
        existing["count"] += count
        if _SOURCE_RANK[source] < _SOURCE_RANK[existing["source"]]:
            existing["source"] = source

    for value, count in ledger_rows:
        add(value, int(count or 0), "ledger")
    for value in rule_categories or []:
        add(value, 0, "rule")
    for value in (DEFAULT_CATEGORIES if defaults is None else defaults):
        add(value, 0, "default")

    return sorted(merged.values(), key=lambda row: (-row["count"], row["value"]))
