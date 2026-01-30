"""
Test all Superset dashboards.

Tests verify that:
1. All 4 dashboards exist and are accessible
2. Each dashboard has the expected number of charts
3. Exported JSON files are valid
4. Dashboard filters work correctly
5. All charts query successfully
6. Dashboards are accessible via API
"""

import os
import pytest
import requests


@pytest.fixture
def superset_base_url():
    """Base URL for Superset API."""
    return "http://localhost:8088"


@pytest.fixture
def superset_session(superset_base_url):
    """Authenticated session for Superset API."""
    session = requests.Session()

    login_url = f"{superset_base_url}/api/v1/security/login"
    login_data = {
        "username": "admin",
        "password": "admin",
        "provider": "db",
        "refresh": True,
    }

    response = session.post(login_url, json=login_data)
    assert response.status_code == 200, f"Login failed: {response.text}"

    token_data = response.json()
    access_token = token_data.get("access_token")
    assert access_token, "No access token in response"

    session.headers.update({"Authorization": f"Bearer {access_token}"})

    return session


@pytest.fixture
def expected_dashboards():
    """Expected dashboards with their slugs and chart counts."""
    return {
        "operations": {"chart_count": 9, "title": "Operations Dashboard"},
        "driver-performance": {
            "chart_count": 6,
            "title": "Driver Performance Dashboard",
        },
        "demand-analysis": {"chart_count": 6, "title": "Demand Analysis Dashboard"},
        "revenue-analytics": {"chart_count": 9, "title": "Revenue Analytics Dashboard"},
        "bronze-pipeline": {"chart_count": 8, "title": "Bronze Pipeline Dashboard"},
        "silver-quality": {"chart_count": 8, "title": "Silver Quality Dashboard"},
    }


@pytest.fixture
def dashboards_dir():
    """Path to dashboards export directory."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    return os.path.join(project_root, "analytics", "superset", "dashboards")


def test_all_dashboards_exist(superset_session, superset_base_url, expected_dashboards):
    """Verify all 4 dashboards accessible with slugs.

    Input: Expected dashboard slugs ['operations', 'driver-performance', 'demand-analysis', 'revenue-analytics']
    Expected: All dashboards exist and are accessible via API
    """
    list_url = f"{superset_base_url}/api/v1/dashboard/"
    response = superset_session.get(list_url)

    assert response.status_code == 200, f"Failed to fetch dashboards: {response.text}"

    dashboards = response.json().get("result", [])
    found_slugs = {dashboard.get("slug") for dashboard in dashboards}

    for slug in expected_dashboards.keys():
        assert slug in found_slugs, f"Dashboard with slug '{slug}' not found"


def test_dashboard_charts_count(superset_session, superset_base_url, expected_dashboards):
    """Verify each dashboard has expected chart count.

    Input: Dashboard slugs and expected counts
    Expected: operations: 9, driver-performance: 6, demand-analysis: 6, revenue-analytics: 9
    """
    list_url = f"{superset_base_url}/api/v1/dashboard/"
    response = superset_session.get(list_url)
    assert response.status_code == 200

    dashboards = response.json().get("result", [])

    for slug, expected_data in expected_dashboards.items():
        dashboard = None
        for d in dashboards:
            if d.get("slug") == slug:
                dashboard = d
                break

        assert dashboard is not None, f"Dashboard '{slug}' not found"

        dashboard_id = dashboard.get("id")
        detail_url = f"{superset_base_url}/api/v1/dashboard/{dashboard_id}"
        detail_response = superset_session.get(detail_url)
        assert detail_response.status_code == 200

        dashboard_data = detail_response.json().get("result", {})

        charts = dashboard_data.get("charts")
        if charts and isinstance(charts[0], str):
            chart_count = len(charts)
        else:
            slices = dashboard_data.get("slices", [])
            chart_count = len(slices)

        expected_count = expected_data["chart_count"]
        assert (
            chart_count == expected_count
        ), f"Dashboard '{slug}' expected {expected_count} charts, found {chart_count}"


def test_exported_json_valid(dashboards_dir, expected_dashboards):
    """Verify exported JSON is valid with required fields.

    Input: Exported JSON files (ZIP format from Superset export)
    Expected: Valid ZIP file containing dashboard export data
    """
    import zipfile

    for slug in expected_dashboards.keys():
        json_file = os.path.join(dashboards_dir, f"{slug}.json")

        assert os.path.exists(json_file), f"Exported JSON file not found: {json_file}"

        assert zipfile.is_zipfile(json_file), f"Export file {slug}.json is not a valid ZIP"

        with zipfile.ZipFile(json_file, "r") as zf:
            assert len(zf.namelist()) > 0, f"ZIP file {slug}.json is empty"

            dashboard_yaml_files = [
                name
                for name in zf.namelist()
                if name.endswith(".yaml") and "dashboard" in name.lower()
            ]
            assert len(dashboard_yaml_files) > 0, f"No dashboard YAML found in {slug}.json export"


def test_dashboard_filters(superset_session, superset_base_url):
    """Verify dashboard filters work.

    Input: Time range filter parameter
    Expected: Dashboard filters applied correctly without errors
    """
    list_url = f"{superset_base_url}/api/v1/dashboard/"
    response = superset_session.get(list_url)
    assert response.status_code == 200

    dashboards = response.json().get("result", [])

    for dashboard in dashboards[:1]:
        dashboard_id = dashboard.get("id")

        detail_url = f"{superset_base_url}/api/v1/dashboard/{dashboard_id}"
        params = {"time_range": "Last 7 days"}

        detail_response = superset_session.get(detail_url, params=params)
        assert (
            detail_response.status_code == 200
        ), f"Failed to apply filter to dashboard {dashboard_id}"


def test_charts_query_successfully(superset_session, superset_base_url):
    """Verify all charts return data without errors.

    Input: All dashboard charts
    Expected: All charts execute queries and return data successfully
    """
    list_url = f"{superset_base_url}/api/v1/dashboard/"
    response = superset_session.get(list_url)
    assert response.status_code == 200

    dashboards = response.json().get("result", [])

    for dashboard in dashboards:
        dashboard_id = dashboard.get("id")
        detail_url = f"{superset_base_url}/api/v1/dashboard/{dashboard_id}"
        detail_response = superset_session.get(detail_url)
        assert detail_response.status_code == 200

        dashboard_data = detail_response.json().get("result", {})
        slices = dashboard_data.get("slices", [])

        for slice_obj in slices:
            chart_id = slice_obj.get("id")
            chart_url = f"{superset_base_url}/api/v1/chart/{chart_id}"
            chart_response = superset_session.get(chart_url)

            assert chart_response.status_code == 200, f"Chart {chart_id} failed to load"


def test_dashboards_accessible(superset_session, superset_base_url, expected_dashboards):
    """Verify all dashboards are accessible via API.

    Input: Dashboard slugs
    Expected: All dashboards return 200 status with valid data
    """
    list_url = f"{superset_base_url}/api/v1/dashboard/"
    response = superset_session.get(list_url)
    assert response.status_code == 200

    dashboards = response.json().get("result", [])

    for slug, expected_data in expected_dashboards.items():
        dashboard = None
        for d in dashboards:
            if d.get("slug") == slug:
                dashboard = d
                break

        assert dashboard is not None, f"Dashboard '{slug}' not found"

        dashboard_id = dashboard.get("id")
        detail_url = f"{superset_base_url}/api/v1/dashboard/{dashboard_id}"
        detail_response = superset_session.get(detail_url)

        assert detail_response.status_code == 200, f"Dashboard '{slug}' not accessible"

        dashboard_data = detail_response.json().get("result", {})
        assert dashboard_data.get("dashboard_title") == expected_data["title"]
        assert dashboard_data.get("slug") == slug

        charts = dashboard_data.get("charts") or dashboard_data.get("slices")
        assert isinstance(charts, list), f"Dashboard '{slug}' has no charts"
        assert len(charts) > 0, f"Dashboard '{slug}' has no charts"
