#!/bin/bash
set -e

# Copy mounted config to writable temp location.
# Bind-mounted /etc/trino may not be writable by the trino user (UID 1000)
# on Linux CI runners where the host files are owned by a different UID.
TRINO_ETC="/tmp/trino-etc"
cp -r /etc/trino "$TRINO_ETC"

# Source credentials from secrets volume (written by secrets-init)
echo "Trino: Loading credentials from secrets volume"
set -a && . /secrets/data-pipeline.env && set +a

# Substitute environment variables in delta.properties template
echo "Trino: Substituting environment variables in delta.properties"

if command -v envsubst > /dev/null 2>&1; then
  envsubst < "$TRINO_ETC/catalog/delta.properties.template" > "$TRINO_ETC/catalog/delta.properties"
else
  sed \
    -e "s|\${MINIO_ROOT_USER}|${MINIO_ROOT_USER}|g" \
    -e "s|\${MINIO_ROOT_PASSWORD}|${MINIO_ROOT_PASSWORD}|g" \
    "$TRINO_ETC/catalog/delta.properties.template" > "$TRINO_ETC/catalog/delta.properties"
fi

echo "Trino: delta.properties generated successfully"

# Start Trino with writable config directory
# (replicates /usr/lib/trino/bin/run-trino logic with custom etc-dir)
launcher_opts=(--etc-dir "$TRINO_ETC")
if ! grep -s -q 'node.id' "$TRINO_ETC/node.properties"; then
    launcher_opts+=("-Dnode.id=${HOSTNAME}")
fi
exec /usr/lib/trino/bin/launcher run "${launcher_opts[@]}"
