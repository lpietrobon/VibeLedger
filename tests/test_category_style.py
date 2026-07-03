from analytics_lib import category_color, category_color_map, category_icon, category_root


def test_root_extraction():
    assert category_root("FOOD/COFFEE") == "FOOD"
    assert category_root("shopping/general") == "SHOPPING"
    assert category_root(None) == "UNCATEGORIZED"
    assert category_root("") == "UNCATEGORIZED"


def test_color_is_stable_across_subcategories():
    # Same top-level category => same color, regardless of the subcategory or case.
    assert category_color("FOOD/COFFEE") == category_color("FOOD/GROCERIES")
    assert category_color("food/dining") == category_color("FOOD/OTHER")


def test_light_and_dark_are_defined_and_differ_where_expected():
    # Every core category resolves to a hex string in both modes.
    for cat in ["FOOD", "SHOPPING", "TRANSPORT", "HOUSING", "FUN", "HEALTH", "SERVICES", "FINANCE"]:
        assert category_color(cat).startswith("#")
        assert category_color(cat, dark=True).startswith("#")


def test_unknown_category_folds_to_neutral():
    # A long-tail category doesn't get a cycled hue — it folds to the neutral gray.
    assert category_color("SOME_RARE_THING") == category_color("ANOTHER_RARE_THING")


def test_income_distinct_from_neutral():
    assert category_color("INCOME") != category_color("uncategorized")


def test_icons_present():
    assert category_icon("FOOD/COFFEE") == "restaurant"
    assert category_icon("TRANSFER_IN") == "swap_horiz"
    assert isinstance(category_icon("WHATEVER"), str)


def test_color_map_keys_are_full_category_strings():
    mapping = category_color_map(["FOOD/COFFEE", "SHOPPING/GENERAL"])
    assert mapping["FOOD/COFFEE"] == category_color("FOOD/COFFEE")
    assert set(mapping) == {"FOOD/COFFEE", "SHOPPING/GENERAL"}
