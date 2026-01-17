#!/usr/bin/env python3
"""
Setup Rideshare Gold Layer database connection in Superset.
"""

import requests
import json
import sys


def setup_database_connection():
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
        sys.exit(1)

    token_data = response.json()
    access_token = token_data.get("access_token")

    # Get CSRF token
    csrf_url = f"{base_url}/api/v1/security/csrf_token/"
    session.headers.update({"Authorization": f"Bearer {access_token}"})
    csrf_response = session.get(csrf_url)
    if csrf_response.status_code != 200:
        print(f"Failed to get CSRF token: {csrf_response.text}")
        sys.exit(1)

    csrf_token = csrf_response.json().get("result")

    session.headers.update(
        {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-CSRFToken": csrf_token,
            "Referer": base_url,
        }
    )

    # Check existing databases
    list_url = f"{base_url}/api/v1/database/"
    response = session.get(list_url)
    if response.status_code == 200:
        databases = response.json().get("result", [])
        print(f"Found {len(databases)} existing databases:")
        for db in databases:
            print(f"  - {db.get('database_name')} (ID: {db.get('id')})")

        # Check if Rideshare Gold Layer already exists
        for db in databases:
            if db.get("database_name") == "Rideshare Gold Layer":
                print(f"\nRideshare Gold Layer already exists with ID: {db.get('id')}")
                return db.get("id")

    # Create database connection using the Superset PostgreSQL database for testing
    # In production this would connect to Spark Thrift Server
    database_config = {
        "database_name": "Rideshare Gold Layer",
        "sqlalchemy_uri": "postgresql+psycopg2://superset:superset@postgres-superset:5432/superset",
        "expose_in_sqllab": True,
        "allow_ctas": False,
        "allow_cvas": False,
        "allow_dml": False,
        "cache_timeout": 300,
        "extra": json.dumps(
            {
                "metadata_params": {},
                "engine_params": {},
                "metadata_cache_timeout": {},
                "schemas_allowed_for_csv_upload": [],
            }
        ),
    }

    create_url = f"{base_url}/api/v1/database/"
    response = session.post(create_url, json=database_config)

    if response.status_code in [200, 201]:
        db_id = response.json().get("id")
        print(f"\nCreated Rideshare Gold Layer database connection (ID: {db_id})")
        return db_id
    else:
        print(f"Failed to create database: {response.text}")
        sys.exit(1)


if __name__ == "__main__":
    setup_database_connection()
