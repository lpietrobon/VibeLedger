from datetime import date

from app.services.search_query import parse_query, suggestion_context


def test_bare_words_become_free_text():
    parsed = parse_query("blue bottle coffee")
    assert parsed.text == ["blue", "bottle", "coffee"]
    assert parsed.is_empty is False


def test_field_tokens_parse():
    parsed = parse_query("merchant:starbucks category:FOOD/DINING account:chase")
    assert parsed.merchant == ["starbucks"]
    assert parsed.category == ["FOOD/DINING"]
    assert parsed.account == ["chase"]
    assert parsed.text == []


def test_cat_alias_and_quoted_values():
    parsed = parse_query('cat:FOOD merchant:"blue bottle"')
    assert parsed.category == ["FOOD"]
    assert parsed.merchant == ["blue bottle"]


def test_amount_bounds_all_forms():
    assert parse_query(">50").amount_min == 50.0
    assert parse_query("<100").amount_max == 100.0
    assert parse_query("amount>25.5").amount_min == 25.5
    combined = parse_query(">10 <20")
    assert (combined.amount_min, combined.amount_max) == (10.0, 20.0)


def test_dates_snap_month_bounds():
    parsed = parse_query("from:2026-02 to:2026-03")
    assert parsed.date_from == date(2026, 2, 1)
    assert parsed.date_to == date(2026, 3, 31)  # month end, not the 1st
    exact = parse_query("from:2026-02-15")
    assert exact.date_from == date(2026, 2, 15)


def test_is_flags_and_legacy_uncat():
    assert parse_query("is:unreviewed").flags == {"unreviewed"}
    assert parse_query("uncat").flags == {"uncategorized"}
    assert parse_query("is:refund is:pending").flags == {"refund", "pending"}


def test_unknown_field_falls_through_to_text():
    """A typo must degrade to a keyword search, not silently match nothing."""
    parsed = parse_query("merchnat:starbucks")
    assert parsed.merchant == []
    assert parsed.text == ["merchnat:starbucks"]


def test_unparsable_date_falls_through_to_text():
    parsed = parse_query("from:notadate")
    assert parsed.date_from is None
    assert parsed.text == ["from:notadate"]


def test_empty_query_is_empty():
    assert parse_query("").is_empty
    assert parse_query(None).is_empty
    assert parse_query("   ").is_empty


def test_suggestion_context_offers_fields_when_empty():
    assert suggestion_context("") == ("field", None, "")
    assert suggestion_context("coffee ")[0] == "field"


def test_suggestion_context_switches_to_values_inside_token():
    context, field_key, active = suggestion_context("merchant:star")
    assert (context, field_key, active) == ("value", "merchant", "merchant:star")
    # alias resolves to the canonical field
    assert suggestion_context("cat:FO")[1] == "category"
    # only the trailing token matters
    assert suggestion_context("coffee account:cha")[1] == "account"
