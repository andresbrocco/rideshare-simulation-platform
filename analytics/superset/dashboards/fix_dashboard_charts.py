#!/usr/bin/env python3
"""Fix dashboard charts association."""

import requests


def fix_dashboard():
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

    # Get current dashboard
    detail_url = f"{base_url}/api/v1/dashboard/1"
    detail_response = session.get(detail_url)
    dashboard = detail_response.json().get("result", {})

    # Chart IDs
    chart_ids = [10, 11, 12, 13, 14, 15, 16, 17, 18]

    # Try updating with charts field
    update_data = {"charts": chart_ids}

    response = session.put(detail_url, json=update_data)
    print(f"Update with charts: {response.status_code}")
    if response.status_code not in [200, 201]:
        print(f"Response: {response.text}")
    else:
        # Verify
        detail_response = session.get(detail_url)
        dashboard = detail_response.json().get("result", {})
        charts = dashboard.get("charts", [])
        print(f"Dashboard now has {len(charts)} charts")

        # Check for slices field
        if "slices" in dashboard:
            slices = dashboard.get("slices", [])
            print(f"Dashboard 'slices' field: {len(slices)} items")


if __name__ == "__main__":
    fix_dashboard()
