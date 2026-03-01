#!/usr/bin/env python3
"""Export DBT tables from DuckDB to S3 as Delta tables.

This script exports silver and gold layer tables from DuckDB to MinIO/S3
as Delta tables so they can be queried by Trino in Grafana dashboards.

Usage:
    python3 export-dbt-to-s3.py              # Export both silver and gold
    python3 export-dbt-to-s3.py --layer silver
    python3 export-dbt-to-s3.py --layer gold
"""

import argparse
import os
import sys
from typing import List, Tuple

import duckdb
from deltalake import write_deltalake


def get_storage_options() -> dict[str, str]:
    """Build storage options dict from environment variables.

    In production (no S3_ENDPOINT set), omit AWS_ENDPOINT_URL and credentials
    so the delta-rs rust backend uses the EC2/Pod Identity credential chain.
    In local dev (S3_ENDPOINT set to MinIO), include the endpoint and explicit
    minioadmin credentials.
    """
    opts: dict[str, str] = {
        "AWS_REGION": os.getenv("AWS_REGION", "us-east-1"),
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }
    endpoint = os.getenv("S3_ENDPOINT") or os.getenv("AWS_ENDPOINT_URL")
    if endpoint:
        # Local dev: explicit MinIO endpoint + credentials
        opts["AWS_ENDPOINT_URL"] = endpoint
        opts["AWS_ACCESS_KEY_ID"] = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
        opts["AWS_SECRET_ACCESS_KEY"] = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
        opts["AWS_ALLOW_HTTP"] = "true"
    return opts


def get_duckdb_path() -> str:
    """Get DuckDB path from environment or use default."""
    return os.getenv("DUCKDB_PATH", "/tmp/rideshare.duckdb")


def list_tables(conn: duckdb.DuckDBPyConnection, schema: str) -> List[str]:
    """List all tables in a schema."""
    query = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}'"
    result = conn.execute(query).fetchall()
    return [row[0] for row in result]


def export_table(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    schema: str,
    bucket: str,
    storage_opts: dict[str, str],
) -> bool:
    """Export a single table to S3 as Delta table.

    Returns True if exported, False if skipped (empty table).
    """
    # Check if table has any rows
    count_query = f"SELECT COUNT(*) FROM {schema}.{table_name}"
    row_count = conn.execute(count_query).fetchone()[0]

    if row_count == 0:
        print(f"  [SKIP] {schema}.{table_name} - empty table (0 rows)")
        return False

    # Fetch table as Arrow table
    select_query = f"SELECT * FROM {schema}.{table_name}"
    arrow_table = conn.execute(select_query).fetch_arrow_table()

    # Write to S3 as Delta table
    s3_path = f"s3a://{bucket}/{table_name}"
    write_deltalake(
        s3_path,
        arrow_table,
        mode="overwrite",
        storage_options=storage_opts,
    )

    print(f"  [OK] {schema}.{table_name} - exported {row_count} rows to {s3_path}")
    return True


def export_layer(
    conn: duckdb.DuckDBPyConnection,
    schema: str,
    bucket: str,
    storage_opts: dict[str, str],
) -> Tuple[int, int]:
    """Export all tables from a layer (silver or gold).

    Returns (exported_count, skipped_count).
    """
    tables = list_tables(conn, schema)

    if not tables:
        print(f"  No tables found in {schema} schema")
        return 0, 0

    exported = 0
    skipped = 0

    for table_name in tables:
        if export_table(conn, table_name, schema, bucket, storage_opts):
            exported += 1
        else:
            skipped += 1

    return exported, skipped


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export DBT tables from DuckDB to S3 as Delta tables"
    )
    parser.add_argument(
        "--layer",
        choices=["silver", "gold"],
        help="Layer to export (silver or gold). If not specified, exports both.",
    )
    args = parser.parse_args()

    duckdb_path = get_duckdb_path()
    storage_opts = get_storage_options()
    silver_bucket = os.getenv("SILVER_BUCKET", "rideshare-silver")
    gold_bucket = os.getenv("GOLD_BUCKET", "rideshare-gold")

    print("=" * 60)
    print("DBT to S3 Delta Export")
    print("=" * 60)
    print(f"DuckDB: {duckdb_path}")
    endpoint = storage_opts.get("AWS_ENDPOINT_URL", "AWS (credential chain)")
    print(f"S3 Endpoint: {endpoint}")
    print(f"Silver bucket: {silver_bucket}")
    print(f"Gold bucket:   {gold_bucket}")
    print()

    # Check if DuckDB file exists
    if not os.path.exists(duckdb_path):
        print(f"ERROR: DuckDB file not found at {duckdb_path}")
        return 1

    # Connect to DuckDB (read-only) and load extensions
    conn = duckdb.connect(duckdb_path, read_only=True)
    conn.execute("LOAD delta")
    conn.execute("LOAD httpfs")

    total_exported = 0
    total_skipped = 0

    try:
        # Export silver layer
        if args.layer is None or args.layer == "silver":
            print("--- Silver Layer ---")
            exported, skipped = export_layer(conn, "silver", silver_bucket, storage_opts)
            total_exported += exported
            total_skipped += skipped
            print()

        # Export gold layer
        if args.layer is None or args.layer == "gold":
            print("--- Gold Layer ---")
            exported, skipped = export_layer(conn, "gold", gold_bucket, storage_opts)
            total_exported += exported
            total_skipped += skipped
            print()

    finally:
        conn.close()

    print("=" * 60)
    print("Export Summary")
    print("=" * 60)
    print(f"  Exported: {total_exported}")
    print(f"  Skipped (empty): {total_skipped}")
    print()
    print("Done")

    return 0


if __name__ == "__main__":
    sys.exit(main())
