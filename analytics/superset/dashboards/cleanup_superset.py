#!/usr/bin/env python3
"""Clean up existing Superset resources before recreating."""

import requests


def cleanup():
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
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return

    token_data = response.json()
    access_token = token_data.get("access_token")
    session.headers.update({"Authorization": f"Bearer {access_token}"})

    # Get CSRF token
    csrf_url = f"{base_url}/api/v1/security/csrf_token/"
    csrf_response = session.get(csrf_url)
    if csrf_response.status_code != 200:
        print("Failed to get CSRF token")
        return

    csrf_token = csrf_response.json().get("result")
    session.headers.update({"X-CSRFToken": csrf_token, "Referer": base_url})

    # Delete dashboards
    dash_url = f"{base_url}/api/v1/dashboard/"
    response = session.get(dash_url)
    if response.status_code == 200:
        dashboards = response.json().get("result", [])
        for dash in dashboards:
            dash_id = dash.get("id")
            session.delete(f"{dash_url}{dash_id}")
            print(f"Deleted dashboard {dash.get('dashboard_title')} (ID: {dash_id})")

    # Delete charts
    chart_url = f"{base_url}/api/v1/chart/"
    response = session.get(chart_url)
    if response.status_code == 200:
        charts = response.json().get("result", [])
        for chart in charts:
            chart_id = chart.get("id")
            session.delete(f"{chart_url}{chart_id}")
            print(f"Deleted chart {chart.get('slice_name')} (ID: {chart_id})")

    # Delete datasets
    dataset_url = f"{base_url}/api/v1/dataset/"
    response = session.get(dataset_url)
    if response.status_code == 200:
        datasets = response.json().get("result", [])
        for ds in datasets:
            ds_id = ds.get("id")
            session.delete(f"{dataset_url}{ds_id}")
            print(f"Deleted dataset {ds.get('table_name')} (ID: {ds_id})")

    print("\nCleanup complete!")


if __name__ == "__main__":
    cleanup()
