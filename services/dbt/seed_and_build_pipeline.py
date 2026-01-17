#!/usr/bin/env python3
"""
Seed bronze data and build the entire DBT pipeline for aggregate table validation.
This script ensures data exists at all layers before validating aggregate tables.
"""

from pyhive import hive
import subprocess
import sys


def run_command(cmd, description):
    """Run a shell command and handle errors"""
    print(f"\n{description}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: {description} failed")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        return False
    print(f"✓ {description} succeeded")
    return True


def seed_bronze_data():
    """Insert comprehensive test data into bronze tables"""
    print("\n" + "=" * 60)
    print("SEEDING BRONZE TABLES")
    print("=" * 60)

    conn = hive.Connection(host="localhost", port=10000, database="default")
    cursor = conn.cursor()

    # Insert bronze_trips (4 events for one complete trip lifecycle)
    print("\nInserting bronze_trips...")
    cursor.execute(
        """
    INSERT INTO bronze_trips VALUES
        ('trip-001', 'trip.requested', CAST('2026-01-15 10:00:00' AS TIMESTAMP), 'T001', 'R001',
         ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
         ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
         'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), NULL,
         CAST('2026-01-15 10:00:01' AS TIMESTAMP)),
        ('trip-002', 'trip.matched', CAST('2026-01-15 10:00:05' AS TIMESTAMP), 'T001', 'R001',
         ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
         ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
         'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), 'D001',
         CAST('2026-01-15 10:00:06' AS TIMESTAMP)),
        ('trip-003', 'trip.started', CAST('2026-01-15 10:05:00' AS TIMESTAMP), 'T001', 'R001',
         ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
         ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
         'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), 'D001',
         CAST('2026-01-15 10:05:01' AS TIMESTAMP)),
        ('trip-004', 'trip.completed', CAST('2026-01-15 10:15:00' AS TIMESTAMP), 'T001', 'R001',
         ARRAY(CAST(-23.550 AS DECIMAL(5,3)), CAST(-46.650 AS DECIMAL(5,3))),
         ARRAY(CAST(-23.560 AS DECIMAL(5,3)), CAST(-46.660 AS DECIMAL(5,3))),
         'PIN', 'PIE', CAST(1.2 AS DECIMAL(2,1)), CAST(25.50 AS DECIMAL(4,2)), 'D001',
         CAST('2026-01-15 10:15:01' AS TIMESTAMP))
    """
    )

    # Refresh table to ensure data is visible
    cursor.execute("REFRESH TABLE bronze_trips")
    cursor.execute("SELECT COUNT(*) FROM bronze_trips")
    count = cursor.fetchone()[0]
    print(f"✓ bronze_trips: {count} rows")

    # Insert bronze_driver_status (driver goes online, then offline)
    print("\nInserting bronze_driver_status...")
    cursor.execute(
        """
    INSERT INTO bronze_driver_status VALUES
        ('status-001', 'D001', CAST('2026-01-15 09:00:00' AS TIMESTAMP), 'online', NULL, 'manual',
         ARRAY(CAST(-23.545 AS DECIMAL(5,3)), CAST(-46.645 AS DECIMAL(5,3))),
         CAST('2026-01-15 09:00:01' AS TIMESTAMP)),
        ('status-002', 'D001', CAST('2026-01-15 17:00:00' AS TIMESTAMP), 'offline', 'online', 'manual',
         ARRAY(CAST(-23.545 AS DECIMAL(5,3)), CAST(-46.645 AS DECIMAL(5,3))),
         CAST('2026-01-15 17:00:01' AS TIMESTAMP))
    """
    )
    cursor.execute("REFRESH TABLE bronze_driver_status")
    cursor.execute("SELECT COUNT(*) FROM bronze_driver_status")
    count = cursor.fetchone()[0]
    print(f"✓ bronze_driver_status: {count} rows")

    # Insert bronze_surge_updates (3 surge events in PIN zone)
    print("\nInserting bronze_surge_updates...")
    cursor.execute(
        """
    INSERT INTO bronze_surge_updates VALUES
        ('surge-001', 'PIN', CAST('2026-01-15 10:00:00' AS TIMESTAMP), CAST(1.0 AS DECIMAL(2,1)),
         CAST(1.2 AS DECIMAL(2,1)), 10, 15, 60, CAST('2026-01-15 10:00:01' AS TIMESTAMP)),
        ('surge-002', 'PIN', CAST('2026-01-15 10:30:00' AS TIMESTAMP), CAST(1.2 AS DECIMAL(2,1)),
         CAST(1.5 AS DECIMAL(2,1)), 8, 20, 60, CAST('2026-01-15 10:30:01' AS TIMESTAMP)),
        ('surge-003', 'PIN', CAST('2026-01-15 10:45:00' AS TIMESTAMP), CAST(1.5 AS DECIMAL(2,1)),
         CAST(1.8 AS DECIMAL(2,1)), 6, 25, 60, CAST('2026-01-15 10:45:01' AS TIMESTAMP))
    """
    )
    cursor.execute("REFRESH TABLE bronze_surge_updates")
    cursor.execute("SELECT COUNT(*) FROM bronze_surge_updates")
    count = cursor.fetchone()[0]
    print(f"✓ bronze_surge_updates: {count} rows")

    # Insert bronze_payments
    print("\nInserting bronze_payments...")
    cursor.execute(
        """
    INSERT INTO bronze_payments VALUES
        ('payment-001', 'PAY001', 'T001', CAST('2026-01-15 10:16:00' AS TIMESTAMP), 'R001', 'D001',
         'credit_card', '****1234', CAST(25.50 AS DECIMAL(4,2)), CAST(25.0 AS DECIMAL(3,1)),
         CAST(6.38 AS DECIMAL(3,2)), CAST(19.12 AS DECIMAL(4,2)), CAST('2026-01-15 10:16:01' AS TIMESTAMP))
    """
    )
    cursor.execute("REFRESH TABLE bronze_payments")
    cursor.execute("SELECT COUNT(*) FROM bronze_payments")
    count = cursor.fetchone()[0]
    print(f"✓ bronze_payments: {count} rows")

    # Insert bronze_ratings
    print("\nInserting bronze_ratings...")
    cursor.execute(
        """
    INSERT INTO bronze_ratings VALUES
        ('rating-001', 'T001', CAST('2026-01-15 10:20:00' AS TIMESTAMP), 'rider', 'R001', 'driver', 'D001',
         CAST(5.0 AS DECIMAL(2,1)), CAST('2026-01-15 10:20:01' AS TIMESTAMP))
    """
    )
    cursor.execute("REFRESH TABLE bronze_ratings")
    cursor.execute("SELECT COUNT(*) FROM bronze_ratings")
    count = cursor.fetchone()[0]
    print(f"✓ bronze_ratings: {count} rows")

    # Insert bronze_drivers
    print("\nInserting bronze_drivers...")
    cursor.execute(
        """
    INSERT INTO bronze_drivers VALUES
        ('driver-profile-001', 'D001', CAST('2026-01-15 09:00:00' AS TIMESTAMP), 'update', 'John Driver',
         'john.driver@example.com', '+5511987654321', 'Toyota', 'Corolla', 2020, 'ABC1234', 'White',
         CAST('2026-01-15 09:00:01' AS TIMESTAMP))
    """
    )
    cursor.execute("REFRESH TABLE bronze_drivers")
    cursor.execute("SELECT COUNT(*) FROM bronze_drivers")
    count = cursor.fetchone()[0]
    print(f"✓ bronze_drivers: {count} rows")

    # Insert bronze_riders
    print("\nInserting bronze_riders...")
    cursor.execute(
        """
    INSERT INTO bronze_riders VALUES
        ('rider-profile-001', 'R001', CAST('2026-01-15 08:00:00' AS TIMESTAMP), 'update', 'Jane Rider',
         'jane.rider@example.com', '+5511912345678', CAST('2026-01-15 08:00:01' AS TIMESTAMP))
    """
    )
    cursor.execute("REFRESH TABLE bronze_riders")
    cursor.execute("SELECT COUNT(*) FROM bronze_riders")
    count = cursor.fetchone()[0]
    print(f"✓ bronze_riders: {count} rows")

    cursor.close()
    conn.close()

    print("\n✓ All bronze data seeded successfully")
    return True


def main():
    """Main pipeline build sequence"""
    print("=" * 60)
    print("AGGREGATE TABLES VALIDATION PIPELINE")
    print("=" * 60)

    # Step 1: Seed bronze data
    if not seed_bronze_data():
        print("\n✗ FAILED: Could not seed bronze data")
        sys.exit(1)

    # Step 2: Build staging layer
    if not run_command(
        "cd /Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt && ./venv/bin/dbt run --select staging",
        "Building staging layer",
    ):
        print("\n✗ FAILED: Staging layer build failed")
        sys.exit(1)

    # Step 3: Build dimension tables
    if not run_command(
        "cd /Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt && ./venv/bin/dbt run --select marts.dimensions",
        "Building dimension tables",
    ):
        print("\n✗ FAILED: Dimension tables build failed")
        sys.exit(1)

    # Step 4: Build fact tables
    if not run_command(
        "cd /Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt && ./venv/bin/dbt run --select marts.facts",
        "Building fact tables",
    ):
        print("\n✗ FAILED: Fact tables build failed")
        sys.exit(1)

    # Step 5: Build aggregate tables
    if not run_command(
        "cd /Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt && ./venv/bin/dbt run --select marts.aggregates",
        "Building aggregate tables",
    ):
        print("\n✗ FAILED: Aggregate tables build failed")
        sys.exit(1)

    # Step 6: Run tests
    if not run_command(
        "cd /Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/dbt && ./venv/bin/dbt test --select marts.aggregates",
        "Testing aggregate tables",
    ):
        print("\n✗ FAILED: Aggregate table tests failed")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✓ PIPELINE VALIDATION COMPLETE")
    print("=" * 60)
    print("\nAll aggregate tables built and tested successfully!")


if __name__ == "__main__":
    main()
