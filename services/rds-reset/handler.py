"""Lambda to reset RDS databases for the rideshare platform.
Runs inside the VPC to reach private RDS. Credentials arrive in the event payload.
"""

import json
import re

import pg8000.dbapi


def validate_identifier(name: str) -> str:
    """Reject anything that isn't a simple lowercase SQL identifier."""
    if not re.match(r"^[a-z_][a-z0-9_]*$", name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    return name


def lambda_handler(event, context):
    host = event["host"]
    port = int(event.get("port", 5432))
    master_password = event["master_password"]
    databases = event.get("databases", [])
    results = []

    for db_config in databases:
        db_name = validate_identifier(db_config["name"])
        role_name = validate_identifier(db_config["role"])
        role_password = db_config["password"]

        try:
            # Connect to 'postgres' db to drop/create target database
            conn = pg8000.dbapi.connect(
                host=host,
                port=port,
                user="postgres",
                password=master_password,
                database="postgres",
            )
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(
                f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{db_name}' AND pid <> pg_backend_pid()"
            )
            cur.execute(f"DROP DATABASE IF EXISTS {db_name}")
            cur.execute(f"CREATE DATABASE {db_name}")
            conn.close()

            # Connect to the new database to set up role + grants
            conn = pg8000.dbapi.connect(
                host=host,
                port=port,
                user="postgres",
                password=master_password,
                database=db_name,
            )
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(f"DROP ROLE IF EXISTS {role_name}")
            cur.execute(f"CREATE ROLE {role_name} WITH LOGIN PASSWORD '{role_password}'")
            cur.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {role_name}")
            cur.execute(f"GRANT ALL PRIVILEGES ON SCHEMA public TO {role_name}")
            conn.close()

            results.append({"database": db_name, "status": "success"})
        except Exception as e:
            results.append({"database": db_name, "status": "error", "message": str(e)})

    has_errors = any(r["status"] == "error" for r in results)
    return {
        "statusCode": 500 if has_errors else 200,
        "body": json.dumps({"results": results}),
    }
