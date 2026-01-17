#!/usr/bin/env python3
"""Debug dashboard structure."""

import requests
import json


def debug():
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

    # Get dashboard details
    detail_url = f"{base_url}/api/v1/dashboard/1"
    detail_response = session.get(detail_url)
    dashboard_data = detail_response.json().get("result", {})

    print("Dashboard fields:")
    for key in sorted(dashboard_data.keys()):
        value = dashboard_data[key]
        if isinstance(value, (str, int, bool, type(None))):
            print(f"  {key}: {value}")
        elif isinstance(value, list):
            print(f"  {key}: [{len(value)} items]")
        elif isinstance(value, dict):
            print(f"  {key}: {{{len(value)} keys}}")
        else:
            print(f"  {key}: {type(value)}")

    print(f"\nmetadata type: {type(dashboard_data.get('metadata'))}")
    print(f"metadata value: {dashboard_data.get('metadata')}")

    print(f"\njson_metadata type: {type(dashboard_data.get('json_metadata'))}")
    print(f"json_metadata value: {dashboard_data.get('json_metadata')}")

    print(f"\nposition_json type: {type(dashboard_data.get('position_json'))}")
    if dashboard_data.get("position_json"):
        pos = json.loads(dashboard_data.get("position_json"))
        print(f"position_json keys: {pos.keys()}")


if __name__ == "__main__":
    debug()
