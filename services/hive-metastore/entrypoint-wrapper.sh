#!/bin/bash
# Wait for PostgreSQL to accept connections before running the Hive entrypoint.
# The default /entrypoint.sh exits immediately on connection failure, which causes
# cascading "unhealthy" errors for downstream containers (trino, delta-table-init).

set -e

DB_HOST="${DB_HOST:-postgres-metastore}"
DB_PORT="${DB_PORT:-5432}"
MAX_RETRIES=30
RETRY_INTERVAL=2

# Source credentials from secrets volume (written by secrets-init)
echo "Hive Metastore: Loading credentials from secrets volume"
set -a && . /secrets/data-pipeline.env && set +a

# Substitute environment variables in hive-site.xml template
echo "Hive Metastore: Substituting environment variables in hive-site.xml"
envsubst < /opt/hive/conf/hive-site.xml.template > /opt/hive/conf/hive-site.xml
echo "Hive Metastore: hive-site.xml generated successfully"

echo "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."

for i in $(seq 1 $MAX_RETRIES); do
  if bash -c "echo > /dev/tcp/${DB_HOST}/${DB_PORT}" 2>/dev/null; then
    echo "PostgreSQL is accepting connections (attempt ${i}/${MAX_RETRIES})."
    exec /entrypoint.sh
  fi
  echo "PostgreSQL not ready (attempt ${i}/${MAX_RETRIES}), retrying in ${RETRY_INTERVAL}s..."
  sleep $RETRY_INTERVAL
done

echo "ERROR: PostgreSQL at ${DB_HOST}:${DB_PORT} not reachable after ${MAX_RETRIES} attempts."
exit 1
