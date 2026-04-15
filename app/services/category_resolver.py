from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Pattern, Protocol


class TransactionLike(Protocol):
    amount: Decimal
    name: str | None
    merchant_name: str | None
    plaid_category_primary: str | None


class AccountLike(Protocol):
    name: str | None


class RuleLike(Protocol):
    id: int
    rank: int
    enabled: bool
    description_regex: str | None
    account_name_regex: str | None
    min_amount: Decimal | None
    max_amount: Decimal | None
    assigned_category: str


class AnnotationLike(Protocol):
    user_category: str | None
    rule_category: str | None


@dataclass(frozen=True)
class CompiledRule:
    id: int
    rank: int
    enabled: bool
    assigned_category: str
    description_regex: str | None
    account_name_regex: str | None
    min_amount: Decimal | None
    max_amount: Decimal | None
    description_pattern: Pattern[str] | None
    account_name_pattern: Pattern[str] | None


@dataclass(frozen=True)
class RuleMatch:
    category: str
    rule_id: int


@dataclass(frozen=True)
class CategoryResolution:
    category: str
    rule_id: int | None


def _normalize_regex(pattern: str | None) -> str | None:
    if pattern is None:
        return None
    normalized = pattern.strip()
    return normalized or None


def _compile_pattern(pattern: str | None, field_name: str, rule_id: int) -> Pattern[str] | None:
    if pattern is None:
        return None

    try:
        return re.compile(pattern)
    except re.error as exc:  # invalid pattern is rejected upstream
        raise ValueError(f"Invalid {field_name} for rule_id={rule_id}: {exc}") from exc


def compile_rules(rules: list[RuleLike]) -> list[CompiledRule]:
    """Validate and compile category rules.

    Rules are sorted by rank ascending and can be evaluated using `find_first_matching_rule`.
    """
    compiled: list[CompiledRule] = []

    for rule in rules:
        description_regex = _normalize_regex(rule.description_regex)
        account_name_regex = _normalize_regex(rule.account_name_regex)

        if (
            description_regex is None
            and account_name_regex is None
            and rule.min_amount is None
            and rule.max_amount is None
        ):
            raise ValueError(f"Rule {rule.id} must define at least one condition")

        if (
            rule.min_amount is not None
            and rule.max_amount is not None
            and rule.min_amount > rule.max_amount
        ):
            raise ValueError(
                f"Rule {rule.id} has invalid amount bounds: min_amount > max_amount"
            )

        compiled.append(
            CompiledRule(
                id=rule.id,
                rank=rule.rank,
                enabled=rule.enabled,
                assigned_category=rule.assigned_category,
                description_regex=description_regex,
                account_name_regex=account_name_regex,
                min_amount=rule.min_amount,
                max_amount=rule.max_amount,
                description_pattern=_compile_pattern(
                    description_regex, "description_regex", rule.id
                ),
                account_name_pattern=_compile_pattern(
                    account_name_regex, "account_name_regex", rule.id
                ),
            )
        )

    return sorted(compiled, key=lambda r: r.rank)


def _matches_rule(rule: CompiledRule, tx: TransactionLike, account: AccountLike) -> bool:
    if not rule.enabled:
        return False

    description_target = tx.name or tx.merchant_name or ""
    account_name_target = account.name or ""
    amount_abs = abs(tx.amount)

    if rule.description_pattern and not rule.description_pattern.search(description_target):
        return False

    if rule.account_name_pattern and not rule.account_name_pattern.search(account_name_target):
        return False

    if rule.min_amount is not None and not (amount_abs > rule.min_amount):
        return False

    if rule.max_amount is not None and not (amount_abs < rule.max_amount):
        return False

    return True


def find_first_matching_rule(
    compiled_rules: list[CompiledRule], tx: TransactionLike, account: AccountLike
) -> RuleMatch | None:
    """First-match behavior: active rules sorted by rank ASC, first match wins."""
    for rule in compiled_rules:
        if _matches_rule(rule, tx=tx, account=account):
            return RuleMatch(category=rule.assigned_category, rule_id=rule.id)
    return None


def resolve_effective_category(
    tx: TransactionLike,
    annotation: AnnotationLike | None,
    rule_match: RuleMatch | None,
) -> CategoryResolution:
    """Precedence: manual user_category > rule_category > plaid_category_primary > uncategorized."""
    user_category = annotation.user_category if annotation else None
    if user_category:
        return CategoryResolution(category=user_category, rule_id=None)

    rule_category = annotation.rule_category if annotation else None
    if rule_category:
        annotation_rule_id = rule_match.rule_id if rule_match else None
        return CategoryResolution(category=rule_category, rule_id=annotation_rule_id)

    if rule_match:
        return CategoryResolution(category=rule_match.category, rule_id=rule_match.rule_id)

    if tx.plaid_category_primary:
        return CategoryResolution(category=tx.plaid_category_primary, rule_id=None)

    return CategoryResolution(category="uncategorized", rule_id=None)


def resolve_category(
    tx: TransactionLike,
    account: AccountLike,
    rules: list[RuleLike],
    annotation: AnnotationLike | None = None,
) -> CategoryResolution:
    compiled = compile_rules(rules)
    rule_match = find_first_matching_rule(compiled, tx=tx, account=account)
    return resolve_effective_category(tx=tx, annotation=annotation, rule_match=rule_match)
