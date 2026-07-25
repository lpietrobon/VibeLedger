"""End-to-end tests for the parsed `q=` search and the suggestions endpoint."""
from datetime import date

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.models import Account, Item, Transaction, TransactionAnnotation
from app.services.security import encrypt_token
from tests.conftest import AUTH_HEADERS


def _seed():
    with SessionLocal() as db:
        item = Item(plaid_item_id="i-search", access_token_encrypted=encrypt_token("t"), status="active")
        db.add(item)
        db.flush()
        checking = Account(plaid_account_id="a-chk", item_id=item.id, name="Chase Checking", mask="1111")
        card = Account(plaid_account_id="a-cc", item_id=item.id, name="Amex Card", mask="2222")
        db.add_all([checking, card])
        db.flush()

        rows = [
            (checking, date(2026, 1, 10), 5.50, "BLUE BOTTLE", "Blue Bottle", "FOOD_AND_DRINK", False),
            (checking, date(2026, 2, 12), 120.00, "COSTCO", "Costco", "GENERAL_MERCHANDISE", True),
            (card, date(2026, 3, 14), 42.00, "BLUE BOTTLE", "Blue Bottle", "FOOD_AND_DRINK", False),
            (card, date(2026, 3, 20), 900.00, "RENT", "Landlord", "RENT_AND_UTILITIES", False),
        ]
        for account, d, amt, name, merchant, cat, reviewed in rows:
            t = Transaction(
                plaid_transaction_id=f"s-{name}-{d}",
                account_id=account.id,
                item_id=item.id,
                date=d,
                amount=amt,
                name=name,
                merchant_name=merchant,
                plaid_category_primary=cat,
                pending=False,
            )
            db.add(t)
            db.flush()
            if reviewed:
                db.add(TransactionAnnotation(transaction_id=t.id, reviewed=True))
        db.commit()


def _names(body):
    return sorted(item["name"] for item in body["items"])


def _search(client, q):
    r = client.get("/transactions", params={"q": q}, headers=AUTH_HEADERS)
    assert r.status_code == 200
    return r.json()


def test_free_text_search():
    _seed()
    with TestClient(app) as client:
        body = _search(client, "blue")
    assert _names(body) == ["BLUE BOTTLE", "BLUE BOTTLE"]
    assert body["total"] == 2


def test_merchant_and_account_tokens():
    _seed()
    with TestClient(app) as client:
        by_merchant = _search(client, "merchant:costco")
        by_account = _search(client, "account:amex")
    assert _names(by_merchant) == ["COSTCO"]
    assert _names(by_account) == ["BLUE BOTTLE", "RENT"]


def test_category_parent_matches_children():
    _seed()
    with TestClient(app) as client:
        parent = _search(client, "category:FOOD")
        exact = _search(client, "category:FOOD/OTHER")
    # FOOD_AND_DRINK maps to the friendly FOOD/OTHER, so the parent matches both.
    assert parent["total"] == 2
    assert exact["total"] == 2


def test_amount_and_date_bounds():
    _seed()
    with TestClient(app) as client:
        over = _search(client, ">100")
        window = _search(client, "from:2026-03 to:2026-03")
    assert _names(over) == ["COSTCO", "RENT"]
    assert _names(window) == ["BLUE BOTTLE", "RENT"]


def test_is_flags():
    _seed()
    with TestClient(app) as client:
        unreviewed = _search(client, "is:unreviewed")
        reviewed = _search(client, "is:reviewed")
    assert reviewed["total"] == 1
    assert _names(reviewed) == ["COSTCO"]
    assert unreviewed["total"] == 3


def test_tokens_combine_with_and():
    _seed()
    with TestClient(app) as client:
        body = _search(client, "merchant:blue account:amex")
    assert _names(body) == ["BLUE BOTTLE"]
    assert body["total"] == 1


def test_suggestions_offer_fields_when_empty():
    _seed()
    with TestClient(app) as client:
        r = client.get("/transactions/search-suggestions", headers=AUTH_HEADERS)
    body = r.json()
    assert body["context"] == "field"
    labels = [s["label"] for s in body["suggestions"]]
    # This menu is what removes the need to remember the syntax.
    assert "Merchant" in labels and "Category" in labels and "Account" in labels


def test_suggestions_return_real_values_inside_token():
    _seed()
    with TestClient(app) as client:
        merchants = client.get(
            "/transactions/search-suggestions", params={"q": "merchant:blue"}, headers=AUTH_HEADERS
        ).json()
        statuses = client.get(
            "/transactions/search-suggestions", params={"q": "is:un"}, headers=AUTH_HEADERS
        ).json()

    assert merchants["context"] == "value"
    assert merchants["field"] == "merchant"
    assert [s["label"] for s in merchants["suggestions"]] == ["Blue Bottle"]
    assert merchants["suggestions"][0]["value"] == 'merchant:"Blue Bottle"'

    assert [s["label"] for s in statuses["suggestions"]] == ["unreviewed", "uncategorized"]


def test_every_is_flag_actually_filters():
    """A flag the grammar accepts but the SQL layer ignores matches everything.

    That failure mode is silent and dangerous: `is:likely-refund` parsed fine
    while the API had no handler for it, so the Overview drill-down that used it
    returned the entire ledger instead of nine refunds. Comparing the compiled
    SQL catches an unwired flag without needing a fixture row per status.
    """
    from app.api.routes import _apply_search_query
    from app.services.search_query import IS_VALUES, parse_query

    with SessionLocal() as db:
        base = (
            db.query(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .outerjoin(TransactionAnnotation, Transaction.id == TransactionAnnotation.transaction_id)
        )
        unfiltered = str(base)

        for flag, _label in IS_VALUES:
            parsed = parse_query(f"is:{flag}")
            assert parsed.flags == {flag}, f"is:{flag} did not parse as a status flag"
            assert str(_apply_search_query(base, parsed)) != unfiltered, (
                f"is:{flag} is offered by the search grammar but adds no SQL filter, "
                "so it silently matches every transaction"
            )
