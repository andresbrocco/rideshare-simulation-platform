"""
Test Operations dashboard in Superset.

Tests verify that:
1. Operations dashboard exists and is accessible
2. All 9 required charts are present
3. Auto-refresh interval is configured
4. Dashboard URL returns valid data
"""

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
def dashboard_slug():
    """Expected dashboard slug."""
    return "operations"


def test_dashboard_exists(superset_session, superset_base_url, dashboard_slug):
    """Verify operations dashboard exists and is accessible via API.

    Input: Dashboard slug 'operations'
    Expected: Dashboard JSON returned with status 200
    """
    list_url = f"{superset_base_url}/api/v1/dashboard/"
    response = superset_session.get(list_url)

    assert response.status_code == 200, f"Failed to fetch dashboards: {response.text}"

    dashboards = response.json().get("result", [])
    operations_dashboard = None

    for dashboard in dashboards:
        if dashboard.get("slug") == dashboard_slug:
            operations_dashboard = dashboard
            break

    assert operations_dashboard is not None, f"Dashboard with slug '{dashboard_slug}' not found"
    assert operations_dashboard.get("dashboard_title") == "Operations Dashboard"


def test_required_charts_present(superset_session, superset_base_url, dashboard_slug):
    """Verify all 9 required charts are present in the dashboard.

    Input: Dashboard JSON
    Expected: Charts for trips, DLQ errors, pipeline health, zone map

    Required charts:
    1. Active Trips
    2. Completed Today
    3. Average Wait Time Today
    4. Total Revenue Today
    5. DLQ Errors Last Hour
    6. Total DLQ Errors
    7. Hourly Trip Volume
    8. Pipeline Lag
    9. Trips by Zone Today
    """
    list_url = f"{superset_base_url}/api/v1/dashboard/"
    response = superset_session.get(list_url)
    assert response.status_code == 200

    dashboards = response.json().get("result", [])
    operations_dashboard = None

    for dashboard in dashboards:
        if dashboard.get("slug") == dashboard_slug:
            operations_dashboard = dashboard
            break

    assert operations_dashboard is not None
    dashboard_id = operations_dashboard.get("id")

    detail_url = f"{superset_base_url}/api/v1/dashboard/{dashboard_id}"
    detail_response = superset_session.get(detail_url)
    assert detail_response.status_code == 200

    dashboard_data = detail_response.json().get("result", {})

    # Check for charts (current API returns list of names) or slices (legacy API returns objects)
    charts = dashboard_data.get("charts")
    if charts and isinstance(charts[0], str):
        # Current API: charts is a list of chart names
        chart_names = charts
    else:
        # Legacy API: slices is a list of chart objects
        slices = dashboard_data.get("slices", [])
        chart_names = [chart.get("slice_name") for chart in slices]

    assert len(chart_names) == 9, f"Expected 9 charts, found {len(chart_names)}"

    required_chart_names = [
        "Active Trips",
        "Completed Today",
        "Average Wait Time Today",
        "Total Revenue Today",
        "DLQ Errors Last Hour",
        "Total DLQ Errors",
        "Hourly Trip Volume",
        "Pipeline Lag",
        "Trips by Zone Today",
    ]

    for required_chart in required_chart_names:
        assert required_chart in chart_names, f"Required chart '{required_chart}' not found"


def test_refresh_interval_configured(superset_session, superset_base_url, dashboard_slug):
    """Verify auto-refresh is enabled with appropriate interval.

    Input: Dashboard JSON
    Expected: refresh_frequency set (e.g., 300 seconds or less)
    """
    list_url = f"{superset_base_url}/api/v1/dashboard/"
    response = superset_session.get(list_url)
    assert response.status_code == 200

    dashboards = response.json().get("result", [])
    operations_dashboard = None

    for dashboard in dashboards:
        if dashboard.get("slug") == dashboard_slug:
            operations_dashboard = dashboard
            break

    assert operations_dashboard is not None
    dashboard_id = operations_dashboard.get("id")

    detail_url = f"{superset_base_url}/api/v1/dashboard/{dashboard_id}"
    detail_response = superset_session.get(detail_url)
    assert detail_response.status_code == 200

    dashboard_data = detail_response.json().get("result", {})

    # Try json_metadata first (current API), fallback to metadata (legacy)
    metadata = dashboard_data.get("json_metadata") or dashboard_data.get("metadata", {})

    if isinstance(metadata, str):
        import json

        metadata = json.loads(metadata)

    refresh_frequency = metadata.get("refresh_frequency")

    assert refresh_frequency is not None, "No refresh_frequency configured"
    assert isinstance(refresh_frequency, int), "refresh_frequency must be an integer"
    assert refresh_frequency <= 300, f"refresh_frequency too high: {refresh_frequency} seconds"


def test_dashboard_accessible(superset_session, superset_base_url, dashboard_slug):
    """Verify dashboard URL returns 200 status and valid data.

    Input: Dashboard slug
    Expected: Dashboard endpoint returns 200 with data
    """
    list_url = f"{superset_base_url}/api/v1/dashboard/"
    response = superset_session.get(list_url)
    assert response.status_code == 200

    dashboards = response.json().get("result", [])
    operations_dashboard = None

    for dashboard in dashboards:
        if dashboard.get("slug") == dashboard_slug:
            operations_dashboard = dashboard
            break

    assert operations_dashboard is not None
    dashboard_id = operations_dashboard.get("id")

    detail_url = f"{superset_base_url}/api/v1/dashboard/{dashboard_id}"
    detail_response = superset_session.get(detail_url)

    assert detail_response.status_code == 200

    dashboard_data = detail_response.json().get("result", {})
    assert dashboard_data.get("dashboard_title") == "Operations Dashboard"
    assert dashboard_data.get("slug") == dashboard_slug

    # Check for charts (current API) or slices (legacy)
    charts = dashboard_data.get("charts") or dashboard_data.get("slices")
    assert isinstance(charts, list)
