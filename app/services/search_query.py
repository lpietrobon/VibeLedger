"""Canonical transaction search grammar.

Parses a free-text query into structured filter tokens. Kept pure (no DB, no
SQLAlchemy) so it can be unit tested directly; the API layer turns the parsed
tokens into SQL. See docs/transaction-search-spec.md.

Design note: unknown `field:value` tokens deliberately fall through to free text
rather than being dropped, so a typo degrades to a keyword search instead of
silently returning nothing.
"""
from __future__ import annotations

import calendar
import re
import shlex
from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class SearchField:
    key: str
    label: str
    hint: str
    #: token prefix the client inserts when this field is picked
    token: str
    #: whether the client should fetch value suggestions after picking it
    has_values: bool


# Ordered as shown in the client dropdown. This list is the single source of the
# "what can I filter on?" answer — the whole point of the redesign.
SEARCH_FIELDS: tuple[SearchField, ...] = (
    SearchField("merchant", "Merchant", "e.g. Blue Bottle", "merchant:", True),
    SearchField("category", "Category", "e.g. FOOD/DINING", "category:", True),
    SearchField("account", "Account", "e.g. Chase Checking", "account:", True),
    SearchField("amount_min", "Amount over", "e.g. >50", ">", False),
    SearchField("amount_max", "Amount under", "e.g. <100", "<", False),
    SearchField("date_from", "From date", "YYYY-MM or YYYY-MM-DD", "from:", False),
    SearchField("date_to", "To date", "YYYY-MM or YYYY-MM-DD", "to:", False),
    SearchField("is", "Status", "unreviewed, uncategorized, refund…", "is:", True),
)

IS_VALUES: tuple[tuple[str, str], ...] = (
    ("unreviewed", "Not yet reviewed"),
    ("reviewed", "Already reviewed"),
    ("uncategorized", "No category assigned"),
    ("refund", "Confirmed or likely refund"),
    ("likely-refund", "Detected refund, not yet confirmed"),
    ("spend", "Posted expense rows, including refunds that reduce spend"),
    ("not-transfer", "Excludes paired transfers"),
    ("pending", "Still pending"),
)

_VALID_IS = {v for v, _ in IS_VALUES}

#: fields whose suggestion values come from the database
VALUE_FIELDS = {"merchant", "category", "account"}


@dataclass
class ParsedQuery:
    merchant: list[str] = field(default_factory=list)
    category: list[str] = field(default_factory=list)
    account: list[str] = field(default_factory=list)
    amount_min: float | None = None
    amount_max: float | None = None
    date_from: date | None = None
    date_to: date | None = None
    flags: set[str] = field(default_factory=set)
    text: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not any(
            [
                self.merchant,
                self.category,
                self.account,
                self.amount_min is not None,
                self.amount_max is not None,
                self.date_from,
                self.date_to,
                self.flags,
                self.text,
            ]
        )


def _parse_date(value: str, *, end: bool) -> date | None:
    """YYYY-MM-DD exact, or YYYY-MM snapped to the first/last day of the month."""
    parts = value.split("-")
    try:
        if len(parts) == 3:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        if len(parts) == 2:
            year, month = int(parts[0]), int(parts[1])
            day = calendar.monthrange(year, month)[1] if end else 1
            return date(year, month, day)
    except (ValueError, IndexError):
        return None
    return None


def _split_tokens(raw: str) -> list[str]:
    """Whitespace split that honors quotes, tolerating unbalanced quotes."""
    try:
        return shlex.split(raw)
    except ValueError:
        return raw.split()


def parse_query(raw: str | None) -> ParsedQuery:
    parsed = ParsedQuery()
    if not raw or not raw.strip():
        return parsed

    for token in _split_tokens(raw.strip()):
        if not token:
            continue

        # Bare comparison forms: >50, <100 (and amount>50 / amount:<100)
        if match := re.fullmatch(r"(?:amount)?[:]?([<>])=?\s*(\d+(?:\.\d+)?)", token, re.I):
            op, number = match.group(1), float(match.group(2))
            if op == ">":
                parsed.amount_min = number
            else:
                parsed.amount_max = number
            continue

        if ":" in token:
            key, _, value = token.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if value:
                if key == "merchant":
                    parsed.merchant.append(value)
                    continue
                if key in {"category", "cat"}:
                    parsed.category.append(value)
                    continue
                if key == "account":
                    parsed.account.append(value)
                    continue
                if key == "from":
                    if (d := _parse_date(value, end=False)) is not None:
                        parsed.date_from = d
                        continue
                if key == "to":
                    if (d := _parse_date(value, end=True)) is not None:
                        parsed.date_to = d
                        continue
                if key == "is" and value.lower() in _VALID_IS:
                    parsed.flags.add(value.lower())
                    continue

            # Unrecognized field or unparsable value: keep it as free text.
            parsed.text.append(token)
            continue

        # Legacy bare shorthand kept working for existing muscle memory.
        if re.fullmatch(r"uncat(?:egorized)?", token, re.I):
            parsed.flags.add("uncategorized")
            continue

        parsed.text.append(token)

    return parsed


def describe_tokens(parsed: ParsedQuery) -> list[dict]:
    """Human-readable chips for the client, each with the token that produced it."""
    chips: list[dict] = []
    for value in parsed.merchant:
        chips.append({"type": "merchant", "label": f"Merchant: {value}", "token": f"merchant:{_quote(value)}"})
    for value in parsed.category:
        chips.append({"type": "category", "label": f"Category: {value}", "token": f"category:{_quote(value)}"})
    for value in parsed.account:
        chips.append({"type": "account", "label": f"Account: {value}", "token": f"account:{_quote(value)}"})
    if parsed.amount_min is not None:
        chips.append({"type": "amount_min", "label": f"Over ${parsed.amount_min:,.0f}", "token": f">{_num(parsed.amount_min)}"})
    if parsed.amount_max is not None:
        chips.append({"type": "amount_max", "label": f"Under ${parsed.amount_max:,.0f}", "token": f"<{_num(parsed.amount_max)}"})
    if parsed.date_from:
        chips.append({"type": "date_from", "label": f"From {parsed.date_from}", "token": f"from:{parsed.date_from}"})
    if parsed.date_to:
        chips.append({"type": "date_to", "label": f"To {parsed.date_to}", "token": f"to:{parsed.date_to}"})
    for flag in sorted(parsed.flags):
        chips.append({"type": "is", "label": flag.replace("-", " ").capitalize(), "token": f"is:{flag}"})
    for value in parsed.text:
        chips.append({"type": "text", "label": f'"{value}"', "token": value})
    return chips


def _quote(value: str) -> str:
    return f'"{value}"' if " " in value else value


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def suggestion_context(raw: str | None) -> tuple[str, str | None, str]:
    """Inspect the in-progress query and decide what to suggest next.

    Returns (context, field_key, active_token) where context is "field" or
    "value". The active token is the trailing fragment the client should replace
    when a suggestion is accepted.
    """
    text = raw or ""
    # The token currently being typed is whatever follows the last space.
    active = text[text.rfind(" ") + 1:] if " " in text else text

    if ":" in active:
        key = active.partition(":")[0].strip().lower()
        if key in {"cat", "category"}:
            return "value", "category", active
        if key in {"merchant", "account", "is"}:
            return "value", key, active
        # Unknown prefix — fall back to offering fields.
        return "field", None, active

    return "field", None, active
