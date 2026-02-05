#!/bin/bash
set -e

echo "Installing dependencies to Superset venv..."
pip install --target=/app/.venv/lib/python3.10/site-packages pyhive thrift psycopg2-binary cachelib

echo "Waiting for PostgreSQL to be fully ready..."
python3 << 'WAIT_EOF'
import time
import psycopg2

max_retries = 30
for i in range(max_retries):
    try:
        conn = psycopg2.connect(
            host="postgres-superset",
            port=5432,
            user="superset",
            password="superset",
            database="superset"
        )
        conn.close()
        print("PostgreSQL is ready!")
        break
    except Exception as e:
        print(f"PostgreSQL not ready ({i+1}/{max_retries}): {e}")
        time.sleep(2)
else:
    print("Failed to connect to PostgreSQL after max retries")
    exit(1)
WAIT_EOF

echo "Running database migrations..."
superset db upgrade

echo "Waiting for migrations to settle..."
sleep 5

echo "Creating admin user..."
superset fab create-admin \
    --username admin \
    --firstname Admin \
    --lastname User \
    --email admin@superset.com \
    --password admin || true

echo "Initializing Superset (with retry)..."
for i in 1 2 3 4 5; do
    superset init && break || {
        echo "Init attempt $i failed, retrying in 5 seconds..."
        sleep 5
    }
done

echo "Superset initialization complete!"
