#!/usr/bin/env python3
"""Register Delta tables in Trino via its REST API.

After DBT exports DuckDB tables to MinIO S3 as Delta tables, Trino still
needs to discover them via Hive Metastore. This script calls
delta.system.register_table() for each table that isn't already registered.

This mirrors the logic of register-delta-tables.sh but uses the Trino REST
API (via requests) so it can run inside the Airflow container which doesn't
have the trino CLI.

Usage:
    python3 register-trino-tables.py --layer silver
    python3 register-trino-tables.py --layer gold
"""

import argparse
import os
import sys
import time
from typing import List

import requests

TRINO_HOST = os.getenv("TRINO_HOST", "trino")
TRINO_PORT = os.getenv("TRINO_PORT", "8080")
TRINO_URL = f"http://{TRINO_HOST}:{TRINO_PORT}"

# Silver tables created by DBT and exported via export-dbt-to-s3.py
# NOTE: anomalies_gps_outliers and anomalies_zombie_drivers are DBT views
# (materialized='view'), not physical tables, so they have no Delta logs
# and cannot be registered as Trino Delta tables.
SILVER_TABLES = [
    "stg_trips",
    "stg_gps_pings",
    "stg_driver_status",
    "stg_surge_updates",
    "stg_ratings",
    "stg_payments",
    "stg_drivers",
    "stg_riders",
    "anomalies_all",
    "anomalies_impossible_speeds",
]

# Gold tables created by DBT and exported via export-dbt-to-s3.py
GOLD_TABLES = [
    "fact_trips",
    "fact_payments",
    "fact_ratings",
    "fact_cancellations",
    "fact_offers",
    "fact_driver_activity",
    "dim_drivers",
    "dim_riders",
    "dim_zones",
    "dim_time",
    "dim_payment_methods",
    "agg_hourly_zone_demand",
    "agg_daily_driver_performance",
    "agg_daily_platform_revenue",
    "agg_surge_history",
]


def execute_trino_sql(sql: str, schema: str = "default") -> List[List[str]]:
    """Submit SQL to Trino REST API and wait for results.

    Returns the result rows as a list of lists. Raises on failure.
    """
    headers = {
        "X-Trino-User": "airflow",
        "X-Trino-Catalog": "delta",
        "X-Trino-Schema": schema,
    }

    resp = requests.post(
        f"{TRINO_URL}/v1/statement",
        data=sql,
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()

    # Poll nextUri until the query completes
    rows: List[List[str]] = []
    while "nextUri" in result:
        time.sleep(0.3)
        resp = requests.get(result["nextUri"], headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        if "data" in result:
            rows.extend(result["data"])

    # Check for errors
    if result.get("error"):
        error_msg = result["error"].get("message", "Unknown Trino error")
        raise RuntimeError(f"Trino query failed: {error_msg}\nSQL: {sql}")

    return rows


def table_exists(table_name: str, schema: str) -> bool:
    """Check if a table is already registered in the Trino schema."""
    rows = execute_trino_sql(f"SHOW TABLES LIKE '{table_name}'", schema)
    return any(table_name in row for row in rows)


def register_table(table_name: str, bucket: str, schema: str) -> bool:
    """Register a single Delta table in Trino.

    Returns True if registered, False if skipped (already exists).
    Raises on unexpected errors.
    """
    if table_exists(table_name, schema):
        print(f"  [SKIP] {table_name} - already registered")
        return False

    location = f"s3a://{bucket}/{table_name}/"
    sql = (
        f"CALL delta.system.register_table("
        f"schema_name => '{schema}', "
        f"table_name => '{table_name}', "
        f"table_location => '{location}')"
    )
    execute_trino_sql(sql, schema)
    print(f"  [OK] {table_name} - registered at {location}")
    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Register Delta tables in Trino via REST API")
    parser.add_argument(
        "--layer",
        choices=["silver", "gold"],
        required=True,
        help="Layer to register (silver or gold)",
    )
    args = parser.parse_args()

    if args.layer == "silver":
        tables = SILVER_TABLES
        bucket = "rideshare-silver"
        schema = "silver"
    else:
        tables = GOLD_TABLES
        bucket = "rideshare-gold"
        schema = "gold"

    print("=" * 60)
    print(f"Trino Delta Table Registration ({args.layer})")
    print("=" * 60)
    print(f"Trino: {TRINO_URL}")
    print(f"Schema: delta.{schema}")
    print(f"Tables: {len(tables)}")
    print()

    # Ensure schema exists
    execute_trino_sql(
        f"CREATE SCHEMA IF NOT EXISTS delta.{schema} " f"WITH (location = 's3a://{bucket}/')"
    )
    print(f"  [OK] delta.{schema} schema ready")
    print()

    registered = 0
    skipped = 0
    failed = 0

    for table_name in tables:
        try:
            if register_table(table_name, bucket, schema):
                registered += 1
            else:
                skipped += 1
        except RuntimeError as exc:
            exc_str = str(exc)
            # "No transaction log found" means the table has no data yet
            # (e.g. stg_ratings/stg_payments before trips complete). Treat
            # as a skippable warning rather than a hard failure so the task
            # doesn't block downstream work.
            if "No transaction log found" in exc_str:
                print(f"  [SKIP] {table_name} - no data in S3 yet (will register on next run)")
                skipped += 1
            else:
                print(f"  [WARN] {table_name} - {exc}")
                failed += 1

    print()
    print("=" * 60)
    print("Registration Summary")
    print("=" * 60)
    print(f"  Registered: {registered}")
    print(f"  Skipped (already registered or no data yet): {skipped}")
    print(f"  Failed: {failed}")
    print()

    if failed > 0:
        print(f"ERROR: {failed} table(s) failed to register (unexpected errors)")
        return 1

    print("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
