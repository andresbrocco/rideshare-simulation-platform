#!/bin/bash
set -e

echo "Installing dependencies (PyHive for Spark, psycopg2 for PostgreSQL)..."
pip install --target=/tmp/python-packages pyhive thrift thrift-sasl pure-sasl psycopg2-binary

# Wait for PostgreSQL metadata database to be ready
# Note: superset-init has already run db upgrade, create-admin, and init
# This container just needs to wait for postgres and provision the Spark connection
echo "Waiting for PostgreSQL metadata database..."
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
        # Verify that superset-init completed by checking for ab_user table
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM ab_user LIMIT 1")
        cursor.close()
        conn.close()
        print("PostgreSQL is ready and initialized!")
        break
    except Exception as e:
        print(f"PostgreSQL/Superset not ready - sleeping... ({i+1}/{max_retries}): {e}")
        time.sleep(2)
else:
    print("Failed to connect to PostgreSQL after max retries")
    exit(1)
WAIT_EOF

# Provision Spark Thrift Server database connection if not exists
echo "Provisioning Spark Thrift Server database connection..."
python3 << 'EOF'
import psycopg2
import uuid

conn = psycopg2.connect(
    host="postgres-superset",
    port=5432,
    user="superset",
    password="superset",
    database="superset"
)
cursor = conn.cursor()

# Check if database already exists
cursor.execute("SELECT id FROM dbs WHERE database_name = %s", ("Rideshare Lakehouse",))
existing = cursor.fetchone()

if existing:
    print("Database 'Rideshare Lakehouse' already exists, skipping creation.")
else:
    # Insert the Spark Thrift Server connection directly
    from datetime import datetime
    db_uuid = str(uuid.uuid4())
    now = datetime.utcnow()
    cursor.execute("""
        INSERT INTO dbs (
            database_name, sqlalchemy_uri, expose_in_sqllab,
            allow_run_async, allow_ctas, allow_cvas, allow_dml,
            cache_timeout, uuid, is_managed_externally, created_on, changed_on, extra,
            impersonate_user, allow_file_upload, configuration_method
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """, (
        "Rideshare Lakehouse",
        "hive://spark-thrift-server:10000/default?auth=NOSASL",
        True,   # expose_in_sqllab
        True,   # allow_run_async
        False,  # allow_ctas
        False,  # allow_cvas
        False,  # allow_dml
        300,    # cache_timeout
        db_uuid,
        False,  # is_managed_externally
        now,    # created_on
        now,    # changed_on
        '{}',   # extra (required JSON field)
        False,  # impersonate_user
        False,  # allow_file_upload
        'sqlalchemy_form'  # configuration_method
    ))
    conn.commit()
    print("Successfully created 'Rideshare Lakehouse' database connection.")

cursor.close()
conn.close()
EOF

echo "Starting Superset server..."

# Start the server in the background and import dashboards once ready
/usr/bin/run-server.sh &
SERVER_PID=$!

# Wait for server to be ready, then import dashboards
echo "Waiting for Superset server to be ready for dashboard import..."
sleep 30  # Give the server time to initialize

# Import dashboards (non-blocking - if it fails, server continues)
if [ -d "/app/dashboards" ]; then
    echo "Importing dashboards..."
    python3 /app/dashboards/import_dashboards.py \
        --base-url http://localhost:8088 \
        --dashboards-dir /app/dashboards 2>&1 || {
        echo "Dashboard import failed (non-blocking), server continues running..."
    }
else
    echo "No dashboards directory mounted, skipping import"
fi

# Wait for server process
wait $SERVER_PID
