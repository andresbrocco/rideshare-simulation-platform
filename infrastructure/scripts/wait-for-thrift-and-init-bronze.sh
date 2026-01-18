#!/bin/bash
set -e

echo "================================================================"
echo "Bronze Layer Initialization Service"
echo "================================================================"

# Wait for Spark Thrift Server to be ready
echo "Waiting for Spark Thrift Server to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
  if nc -z spark-thrift-server 10000 2>/dev/null; then
    echo "✓ Spark Thrift Server is ready"
    break
  fi

  RETRY_COUNT=$((RETRY_COUNT + 1))
  echo "  Attempt $RETRY_COUNT/$MAX_RETRIES: Thrift Server not ready yet, waiting..."
  sleep 5
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "✗ Timed out waiting for Spark Thrift Server"
  exit 1
fi

# Additional wait to ensure Thrift Server is fully initialized
echo "Waiting additional 5 seconds for Thrift Server to fully initialize..."
sleep 5

# Run Bronze initialization
echo "Running Bronze metastore initialization..."
python3 /opt/init-scripts/init-bronze-metastore.py

# Exit with success code
echo "================================================================"
echo "✓ Bronze initialization complete"
echo "================================================================"
exit 0
