"""Tests for GET /categories — the vocabulary offered by category pickers."""
from datetime import date

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import (
    Account,
    CategoryRule,
    Item,
    Transaction,
    TransactionAnnotation,
)
from app.services.category_catalog import (
    DEFAULT_CATEGORIES,
    merge_catalog,
    normalize_category,
)
from app.services.category_resolver import (
    PLAID_DETAILED_FRIENDLY_MAP,
    PLAID_FRIENDLY_MAP,
)
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def _seed():
    """Two FOOD txns, a 1-level pass-through, a deep manual category, and a
    transaction that falls through to the lowercase 'uncategorized' literal."""
    with SessionLocal() as db:
        item = Item(plaid_item_id="i-cat", access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        account = Account(plaid_account_id="a-cat", item_id=item.id, name="Checking")
        db.add(account)
        db.flush()

        def add(name, amount, plaid_cat, user_cat=None):
            t = Transaction(
                plaid_transaction_id=f"c-{name}",
                account_id=account.id,
                item_id=item.id,
                date=date(2026, 5, 1),
                amount=amount,
                name=name,
                plaid_category_primary=plaid_cat,
                pending=False,
            )
            db.add(t)
            db.flush()
            if user_cat:
                db.add(TransactionAnnotation(transaction_id=t.id, user_category=user_cat))
            return t

        add("Groceries", 40.0, "FOOD_AND_DRINK")       # -> FOOD/OTHER
        add("Coffee", 5.0, "FOOD_AND_DRINK")           # -> FOOD/OTHER
        add("Wire", 20.0, "TRANSFER_IN")               # 1-level pass-through
        add("Sushi", 30.0, None, "FOOD/DINING/SUSHI")  # 3-level manual
        add("Mystery", 9.0, None)                      # -> 'uncategorized' literal
        db.commit()


def _by_value(body):
    return {row["value"]: row for row in body["items"]}


def test_ledger_categories_with_counts_ordered_desc():
    _seed()
    with TestClient(app) as client:
        body = client.get("/categories", headers=AUTH_HEADERS).json()
    rows = _by_value(body)
    assert rows["FOOD/OTHER"]["count"] == 2
    assert rows["FOOD/OTHER"]["source"] == "ledger"
    counts = [row["count"] for row in body["items"]]
    assert counts == sorted(counts, reverse=True)


def test_one_level_and_deep_values_survive_intact():
    _seed()
    with TestClient(app) as client:
        rows = _by_value(client.get("/categories", headers=AUTH_HEADERS).json())
    assert rows["TRANSFER_IN"]["count"] == 1        # 1-level pass-through
    assert rows["FOOD/DINING/SUSHI"]["count"] == 1  # 3 levels, no special-casing


def test_case_variants_collapse_into_one_row():
    """The SQL fallback literal is lowercase 'uncategorized'; a manual override
    is "UNCATEGORIZED". They must be one row with summed counts, not two."""
    _seed()
    with SessionLocal() as db:
        tx = db.query(Transaction).filter(Transaction.name == "Wire").one()
        db.add(TransactionAnnotation(transaction_id=tx.id, user_category="UNCATEGORIZED"))
        db.commit()

    with TestClient(app) as client:
        body = client.get("/categories", headers=AUTH_HEADERS).json()
    matches = [r for r in body["items"] if r["value"].upper() == "UNCATEGORIZED"]
    assert len(matches) == 1
    assert matches[0]["value"] == "UNCATEGORIZED"
    assert matches[0]["count"] == 2  # the literal + the manual override


def test_rule_targets_appear_even_with_no_matching_transactions():
    _seed()
    with SessionLocal() as db:
        db.add(CategoryRule(rank=1, enabled=True, description_regex="vet", assigned_category="PETS/VET"))
        db.commit()

    with TestClient(app) as client:
        rows = _by_value(client.get("/categories", headers=AUTH_HEADERS).json())
    assert rows["PETS/VET"]["count"] == 0
    assert rows["PETS/VET"]["source"] == "rule"


def test_defaults_merged_but_never_shadow_real_data():
    _seed()
    with TestClient(app) as client:
        rows = _by_value(client.get("/categories", headers=AUTH_HEADERS).json())
    # unused default present with no count...
    assert rows["FOOD/COFFEE"] == {"value": "FOOD/COFFEE", "count": 0, "source": "default"}
    # ...but a default that IS in use keeps its ledger count and source.
    assert rows["FOOD/OTHER"]["source"] == "ledger"
    assert rows["FOOD/OTHER"]["count"] == 2


def test_empty_ledger_still_returns_defaults():
    """A fresh install must never show an empty picker."""
    with TestClient(app) as client:
        body = client.get("/categories", headers=AUTH_HEADERS).json()
    assert len(body["items"]) == len(DEFAULT_CATEGORIES)
    assert all(row["source"] == "default" for row in body["items"])


def test_requires_auth():
    with TestClient(app) as client:
        assert client.get("/categories").status_code == 401


def test_defaults_cover_every_plaid_mapping_target():
    """Guards against drift: if a friendly-map target isn't in the starter set,
    that category would be missing from every picker until it's used."""
    targets = set(PLAID_FRIENDLY_MAP.values()) | set(PLAID_DETAILED_FRIENDLY_MAP.values())
    assert targets <= set(DEFAULT_CATEGORIES)


def test_normalize_category_matches_frontend_rules():
    assert normalize_category("  food / dining ") == "FOOD_/_DINING"
    assert normalize_category("food and drink") == "FOOD_AND_DRINK"
    assert normalize_category("FOOD//DINING") == "FOOD/DINING"
    assert normalize_category("") == ""
    assert normalize_category(None) == ""


def test_merge_catalog_is_pure_and_sums_case_variants():
    merged = merge_catalog(
        ledger_rows=[("uncategorized", 3), ("UNCATEGORIZED", 2), ("FOOD/OTHER", 1)],
        rule_categories=["PETS/VET"],
        defaults=["FOOD/COFFEE"],
    )
    by_value = {row["value"]: row for row in merged}
    assert by_value["UNCATEGORIZED"]["count"] == 5
    assert by_value["PETS/VET"]["source"] == "rule"
    assert by_value["FOOD/COFFEE"]["source"] == "default"
    assert [row["value"] for row in merged][0] == "UNCATEGORIZED"  # highest count first
