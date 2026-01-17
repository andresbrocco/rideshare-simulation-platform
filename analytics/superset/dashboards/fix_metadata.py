#!/usr/bin/env python3
"""Fix dashboard metadata field."""

import requests
import json


def fix_metadata():
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
    detail_url = f"{base_url}/api/v1/dashboard/{dashboard_id}"

    # Update metadata - try as a JSON string (deprecated field)
    metadata_dict = {"refresh_frequency": 300, "color_scheme": "supersetColors"}

    update_data = {"metadata": json.dumps(metadata_dict)}

    response = session.put(detail_url, json=update_data)
    if response.status_code in [200, 201]:
        print("Updated metadata field")
    else:
        print(f"Failed to update metadata: {response.status_code}")
        print(f"Response: {response.text}")

    # Verify
    detail_response = session.get(detail_url)
    dashboard = detail_response.json().get("result", {})
    print(f"\nmetadata: {dashboard.get('metadata')}")
    print(f"json_metadata: {dashboard.get('json_metadata')}")


if __name__ == "__main__":
    fix_metadata()
