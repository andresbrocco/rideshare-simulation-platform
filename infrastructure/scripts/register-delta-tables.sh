#!/bin/bash
set -e

# Register Delta table locations in Hive Metastore via Trino.
#
# After the Spark-to-DuckDB migration, Python bronze ingestion (delta-rs)
# writes Delta tables directly to S3 without registering them in Hive
# Metastore. Trino needs Hive Metastore to discover tables for BI queries.
#
# This script uses Trino's register_table procedure to register existing
# Delta tables. It is idempotent - safe to re-run at any time.
#
# Usage:
#   Runs automatically as a one-shot Docker init container.
#   Can also be run manually:
#     docker exec rideshare-trino /bin/bash /opt/init-scripts/register-delta-tables.sh

TRINO_HOST="${TRINO_HOST:-trino}"
TRINO_PORT="${TRINO_PORT:-8080}"

# Bronze tables created by bronze-ingestion service (delta-rs)
BRONZE_TABLES=(
    bronze_gps_pings
    bronze_trips
    bronze_driver_status
    bronze_surge_updates
    bronze_ratings
    bronze_payments
    bronze_driver_profiles
    bronze_rider_profiles
)

# DLQ tables created by bronze-ingestion for failed messages
DLQ_TABLES=(
    dlq_bronze_gps_pings
    dlq_bronze_trips
    dlq_bronze_driver_status
    dlq_bronze_surge_updates
    dlq_bronze_ratings
    dlq_bronze_payments
    dlq_bronze_driver_profiles
    dlq_bronze_rider_profiles
)

# Silver tables created by DBT and exported via export-dbt-to-s3.py
SILVER_TABLES=(
    stg_trips
    stg_gps_pings
    stg_driver_status
    stg_surge_updates
    stg_ratings
    stg_payments
    stg_drivers
    stg_riders
    anomalies_all
    anomalies_gps_outliers
    anomalies_impossible_speeds
    anomalies_zombie_drivers
)

# Gold tables created by DBT and exported via export-dbt-to-s3.py
GOLD_TABLES=(
    fact_trips
    fact_payments
    fact_ratings
    fact_cancellations
    fact_driver_activity
    dim_drivers
    dim_riders
    dim_zones
    dim_time
    dim_payment_methods
    agg_hourly_zone_demand
    agg_daily_driver_performance
    agg_daily_platform_revenue
    agg_surge_history
)

REGISTERED=0
SKIPPED=0
FAILED=0

execute_trino() {
    local sql="$1"
    local schema="${2:-default}"
    trino --server "http://${TRINO_HOST}:${TRINO_PORT}" \
          --catalog delta \
          --schema "$schema" \
          --execute "$sql" 2>&1
}

wait_for_trino() {
    local max_retries=30
    local attempt=0

    echo "Waiting for Trino to be ready at ${TRINO_HOST}:${TRINO_PORT}..."

    while [ "$attempt" -lt "$max_retries" ]; do
        if execute_trino "SELECT 1" > /dev/null 2>&1; then
            echo "Trino is ready"
            return 0
        fi

        attempt=$((attempt + 1))
        echo "  Attempt ${attempt}/${max_retries}: Trino not ready, waiting 5s..."
        sleep 5
    done

    echo "ERROR: Timed out waiting for Trino after $((max_retries * 5))s"
    return 1
}

register_table() {
    local table_name="$1"
    local bucket="$2"
    local schema="$3"
    local location="s3a://${bucket}/${table_name}/"

    # Check if table is already registered in Hive Metastore
    local existing
    existing=$(execute_trino "SHOW TABLES LIKE '${table_name}'" "$schema" 2>/dev/null || true)
    if echo "$existing" | grep -q "${table_name}"; then
        echo "  [SKIP] ${table_name} - already registered"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    # Try to register existing Delta table (requires _delta_log at location)
    local output
    local exit_code
    output=$(execute_trino "CALL delta.system.register_table(schema_name => '${schema}', table_name => '${table_name}', table_location => '${location}')" "$schema" 2>&1) && exit_code=0 || exit_code=$?

    if [ "$exit_code" -eq 0 ]; then
        echo "  [OK] ${table_name} - registered at ${location}"
        REGISTERED=$((REGISTERED + 1))
        return 0
    fi

    # Registration failed - likely no Delta log at the location yet
    echo "  [WARN] ${table_name} - not found at ${location} (data not ingested yet)"
    FAILED=$((FAILED + 1))
    return 0
}

echo "=============================================="
echo "Delta Table Registration"
echo "=============================================="
echo "Trino: ${TRINO_HOST}:${TRINO_PORT}"
echo ""

wait_for_trino

echo ""
echo "--- Creating Schemas ---"
execute_trino "CREATE SCHEMA IF NOT EXISTS delta.bronze WITH (location = 's3a://rideshare-bronze/')"
echo "  [OK] delta.bronze schema created"

execute_trino "CREATE SCHEMA IF NOT EXISTS delta.silver WITH (location = 's3a://rideshare-silver/')"
echo "  [OK] delta.silver schema created"

execute_trino "CREATE SCHEMA IF NOT EXISTS delta.gold WITH (location = 's3a://rideshare-gold/')"
echo "  [OK] delta.gold schema created"

echo ""
echo "--- Bronze Tables (${#BRONZE_TABLES[@]}) ---"
for table in "${BRONZE_TABLES[@]}"; do
    register_table "$table" "rideshare-bronze" "bronze"
done

echo ""
echo "--- DLQ Tables (${#DLQ_TABLES[@]}) ---"
for table in "${DLQ_TABLES[@]}"; do
    register_table "$table" "rideshare-bronze" "bronze"
done

echo ""
echo "--- Silver Tables (${#SILVER_TABLES[@]}) ---"
for table in "${SILVER_TABLES[@]}"; do
    register_table "$table" "rideshare-silver" "silver"
done

echo ""
echo "--- Gold Tables (${#GOLD_TABLES[@]}) ---"
for table in "${GOLD_TABLES[@]}"; do
    register_table "$table" "rideshare-gold" "gold"
done

echo ""
echo "=============================================="
echo "Registration Summary"
echo "=============================================="
echo "  Bronze: ${#BRONZE_TABLES[@]} tables"
echo "  DLQ: ${#DLQ_TABLES[@]} tables"
echo "  Silver: ${#SILVER_TABLES[@]} tables"
echo "  Gold: ${#GOLD_TABLES[@]} tables"
echo ""
echo "  Registered: ${REGISTERED}"
echo "  Skipped (already registered): ${SKIPPED}"
echo "  Not found (no data yet): ${FAILED}"
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo "Some tables had no data yet. They will be registered"
    echo "on the next run after bronze-ingestion writes data."
    echo ""
    echo "Re-run with:"
    echo "  docker compose -f infrastructure/docker/compose.yml restart delta-table-init"
fi

echo "Done"
