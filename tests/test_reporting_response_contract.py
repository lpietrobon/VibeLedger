"""Structural API contracts consumed directly by the React reporting client."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import AUTH_HEADERS


REPORTING_SCOPE_FIELDS = {
    "currency",
    "currency_status",
    "currencies",
    "history_coverage",
    "duplicate_account_coverage",
    "qualification",
    "start_date",
    "end_date",
    "recorded_row_count",
    "first_recorded_date",
    "last_recorded_date",
}


def assert_reporting_contract(payload):
    reporting = payload.get("reporting")
    assert isinstance(reporting, dict), "response must include reporting metadata"
    assert REPORTING_SCOPE_FIELDS <= reporting.keys()
    assert {
        "reporting_date",
        "current_period",
        "previous_period",
        "comparison_available",
        "comparison_qualification",
    } <= reporting.keys()
    for period in ("current_period", "previous_period"):
        assert isinstance(reporting[period], dict)
        assert REPORTING_SCOPE_FIELDS <= reporting[period].keys()
    assert reporting["currency_status"] in {"empty", "unknown", "mixed", "single"}
    assert isinstance(reporting["comparison_available"], bool)


@pytest.mark.parametrize(
    "path",
    ["/analytics/overview", "/analytics/spending-summary"],
)
def test_react_reporting_endpoints_share_complete_metadata_contract(path):
    with TestClient(app) as client:
        response = client.get(path, headers=AUTH_HEADERS)
    assert response.status_code == 200
    assert_reporting_contract(response.json())
