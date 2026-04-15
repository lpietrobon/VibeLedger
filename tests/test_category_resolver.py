from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.services.category_resolver import (
    compile_rules,
    find_first_matching_rule,
    resolve_effective_category,
)


@dataclass
class Tx:
    amount: Decimal
    name: str | None
    merchant_name: str | None
    plaid_category_primary: str | None


@dataclass
class Account:
    name: str | None


@dataclass
class Rule:
    id: int
    rank: int
    enabled: bool
    description_regex: str | None
    account_name_regex: str | None
    min_amount: Decimal | None
    max_amount: Decimal | None
    assigned_category: str


@dataclass
class Annotation:
    user_category: str | None = None
    rule_category: str | None = None


def test_find_first_match_uses_lowest_rank():
    tx = Tx(amount=Decimal("12.50"), name="starbucks main", merchant_name=None, plaid_category_primary="DINING")
    account = Account(name="Daily Checking")
    rules = [
        Rule(1, 10, True, "starbucks", None, None, None, "coffee-high-rank"),
        Rule(2, 1, True, "starbucks", None, None, None, "coffee-low-rank"),
    ]

    compiled = compile_rules(rules)
    match = find_first_matching_rule(compiled, tx=tx, account=account)

    assert match is not None
    assert match.rule_id == 2
    assert match.category == "coffee-low-rank"


def test_non_null_rule_conditions_are_anded():
    rule = Rule(10, 1, True, "starbucks", "checking", Decimal("9.00"), Decimal("13.00"), "coffee")
    compiled = compile_rules([rule])

    tx_good = Tx(amount=Decimal("11.00"), name="starbucks 123", merchant_name=None, plaid_category_primary="DINING")
    account_good = Account(name="my checking")
    assert find_first_matching_rule(compiled, tx=tx_good, account=account_good) is not None

    # Same description/account but amount condition fails.
    tx_bad_amount = Tx(amount=Decimal("20.00"), name="starbucks 123", merchant_name=None, plaid_category_primary="DINING")
    assert find_first_matching_rule(compiled, tx=tx_bad_amount, account=account_good) is None


def test_regex_amount_and_account_combo_matching():
    compiled = compile_rules(
        [
            Rule(
                id=33,
                rank=2,
                enabled=True,
                description_regex=r"uber\s+trip",
                account_name_regex=r"visa$",
                min_amount=Decimal("5.00"),
                max_amount=Decimal("30.00"),
                assigned_category="transport",
            )
        ]
    )

    tx_match = Tx(amount=Decimal("18.25"), name="uber trip", merchant_name=None, plaid_category_primary="TRANSPORTATION")
    acct_match = Account(name="travel visa")
    match = find_first_matching_rule(compiled, tx=tx_match, account=acct_match)
    assert match is not None
    assert match.rule_id == 33
    assert match.category == "transport"

    tx_fail_regex = Tx(amount=Decimal("18.25"), name="lyft ride", merchant_name=None, plaid_category_primary="TRANSPORTATION")
    assert find_first_matching_rule(compiled, tx=tx_fail_regex, account=acct_match) is None


def test_effective_category_precedence_manual_rule_plaid_uncategorized():
    tx = Tx(amount=Decimal("3.00"), name="snack", merchant_name=None, plaid_category_primary="PLAID_CAT")
    rule_match = find_first_matching_rule(
        compile_rules([Rule(77, 1, True, "snack", None, None, None, "rule-matched")]),
        tx=tx,
        account=Account(name="Checking"),
    )

    manual = resolve_effective_category(tx, annotation=Annotation(user_category="manual", rule_category="rule-annotated"), rule_match=rule_match)
    assert manual.category == "manual"
    assert manual.rule_id is None

    rule_annotation = resolve_effective_category(tx, annotation=Annotation(user_category=None, rule_category="rule-annotated"), rule_match=rule_match)
    assert rule_annotation.category == "rule-annotated"
    assert rule_annotation.rule_id == 77

    plaid = resolve_effective_category(
        Tx(amount=Decimal("3.00"), name="Snack", merchant_name=None, plaid_category_primary="PLAID_ONLY"),
        annotation=None,
        rule_match=None,
    )
    assert plaid.category == "PLAID_ONLY"
    assert plaid.rule_id is None

    uncategorized = resolve_effective_category(
        Tx(amount=Decimal("3.00"), name="Snack", merchant_name=None, plaid_category_primary=None),
        annotation=None,
        rule_match=None,
    )
    assert uncategorized.category == "uncategorized"
    assert uncategorized.rule_id is None


def test_invalid_regex_is_rejected():
    with pytest.raises(ValueError, match="Invalid description_regex"):
        compile_rules(
            [
                Rule(
                    id=55,
                    rank=0,
                    enabled=True,
                    description_regex="(",
                    account_name_regex=None,
                    min_amount=None,
                    max_amount=None,
                    assigned_category="broken",
                )
            ]
        )
