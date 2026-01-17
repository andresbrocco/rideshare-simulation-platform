#!/usr/bin/env python3
"""Associate charts with dashboard by updating each chart."""

import requests


def associate_charts():
    base_url = "http://localhost:8088"
    session = requests.Session()

    # Login
    login_url = f"{base_url}/api/v1/security/login"
    login_data = {
        "username": "admin",
        "password": "admin",
        "provider": "db",
        "refresh": True,
    }
    response = session.post(login_url, json=login_data)
    token_data = response.json()
    access_token = token_data.get("access_token")
    session.headers.update({"Authorization": f"Bearer {access_token}"})

    # Get CSRF token
    csrf_url = f"{base_url}/api/v1/security/csrf_token/"
    csrf_response = session.get(csrf_url)
    csrf_token = csrf_response.json().get("result")
    session.headers.update(
        {
            "X-CSRFToken": csrf_token,
            "Referer": base_url,
            "Content-Type": "application/json",
        }
    )

    dashboard_id = 1
    chart_ids = [10, 11, 12, 13, 14, 15, 16, 17, 18]

    # Try updating each chart to belong to the dashboard
    for chart_id in chart_ids:
        chart_url = f"{base_url}/api/v1/chart/{chart_id}"

        # Get current chart
        get_response = session.get(chart_url)
        if get_response.status_code != 200:
            print(f"Failed to get chart {chart_id}")
            continue

        # Update with dashboards
        update_data = {"dashboards": [dashboard_id]}

        response = session.put(chart_url, json=update_data)
        if response.status_code in [200, 201]:
            print(f"Associated chart {chart_id} with dashboard {dashboard_id}")
        else:
            print(f"Failed to update chart {chart_id}: {response.status_code}")
            print(f"Response: {response.text}")

    # Verify dashboard has charts
    detail_url = f"{base_url}/api/v1/dashboard/{dashboard_id}"
    detail_response = session.get(detail_url)
    dashboard = detail_response.json().get("result", {})
    charts = dashboard.get("charts", [])
    print(f"\nDashboard now has {len(charts)} charts")


if __name__ == "__main__":
    associate_charts()
