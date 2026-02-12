#!/bin/bash
set -e

# Source credentials from secrets volume (written by secrets-init)
echo "Trino: Loading credentials from secrets volume"
set -a && . /secrets/data-pipeline.env && set +a

# Substitute environment variables in delta.properties template
echo "Trino: Substituting environment variables in delta.properties"

if command -v envsubst > /dev/null 2>&1; then
  envsubst < /etc/trino/catalog/delta.properties.template > /etc/trino/catalog/delta.properties
else
  sed \
    -e "s|\${MINIO_ROOT_USER}|${MINIO_ROOT_USER}|g" \
    -e "s|\${MINIO_ROOT_PASSWORD}|${MINIO_ROOT_PASSWORD}|g" \
    /etc/trino/catalog/delta.properties.template > /etc/trino/catalog/delta.properties
fi

echo "Trino: delta.properties generated successfully"

# Start Trino with original entrypoint
exec /usr/lib/trino/bin/run-trino
