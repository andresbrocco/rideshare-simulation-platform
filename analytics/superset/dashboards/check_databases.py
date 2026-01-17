#!/usr/bin/env python3
"""Check available databases in Superset."""

import requests


def check_databases():
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

    # List databases
    list_url = f"{base_url}/api/v1/database/"
    response = session.get(list_url)
    if response.status_code == 200:
        result = response.json()
        databases = result.get("result", [])
        print(f"Found {len(databases)} databases:")
        for db in databases:
            print(f"  - {db.get('database_name')} (ID: {db.get('id')})")
            print(f"    URI: {db.get('sqlalchemy_uri')}")
            print()
    else:
        print(f"Failed to fetch databases: {response.text}")


if __name__ == "__main__":
    check_databases()
