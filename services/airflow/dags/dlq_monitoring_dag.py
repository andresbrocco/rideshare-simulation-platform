"""DLQ monitoring DAG that checks error counts every 15 minutes.

Connects to MinIO via DuckDB to query DLQ Delta tables for recent errors.
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.standard.operators.python import (
    PythonOperator,
    BranchPythonOperator,
)
from airflow.providers.standard.operators.empty import EmptyOperator

ERROR_THRESHOLD = 10
MINIO_ENDPOINT = os.environ.get("AWS_ENDPOINT_URL")
BRONZE_BUCKET = os.environ.get("BRONZE_BUCKET", "rideshare-bronze")

DLQ_TABLES = [
    "dlq_bronze_trips",
    "dlq_bronze_gps_pings",
    "dlq_bronze_driver_status",
    "dlq_bronze_surge_updates",
    "dlq_bronze_ratings",
    "dlq_bronze_payments",
    "dlq_bronze_driver_profiles",
    "dlq_bronze_rider_profiles",
]

default_args = {
    "owner": "rideshare",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def query_dlq_errors(**context):
    """Query all DLQ tables for error counts in the last 15 minutes.

    Uses DuckDB with delta and httpfs extensions to read Delta tables
    directly from MinIO without requiring Spark.
    """
    import duckdb
    from datetime import datetime, timedelta

    error_counts = {}
    total_errors = 0
    cutoff_time = (datetime.now() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

    try:
        conn = duckdb.connect(":memory:")
        conn.install_extension("delta")
        conn.install_extension("httpfs")
        conn.load_extension("delta")
        conn.load_extension("httpfs")

        if MINIO_ENDPOINT:
            # Local dev: point DuckDB at MinIO with static credentials
            access_key = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
            secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin")
            endpoint_host = MINIO_ENDPOINT.replace("http://", "").replace("https://", "")
            use_ssl = "false" if MINIO_ENDPOINT.startswith("http://") else "true"
            conn.execute(
                f"""
                CREATE SECRET minio_secret (
                    TYPE S3,
                    KEY_ID '{access_key}',
                    SECRET '{secret_key}',
                    ENDPOINT '{endpoint_host}',
                    USE_SSL {use_ssl},
                    URL_STYLE 'path'
                )
            """
            )
        else:
            # Production: use IRSA/Pod Identity credential chain
            region = os.environ.get("AWS_REGION", "us-east-1")
            conn.execute(
                f"""
                CREATE SECRET aws_secret (
                    TYPE S3,
                    PROVIDER CREDENTIAL_CHAIN,
                    REGION '{region}'
                )
            """
            )

        for table in DLQ_TABLES:
            try:
                query = f"""
                    SELECT COUNT(*) as cnt
                    FROM delta_scan('s3://{BRONZE_BUCKET}/{table}/')
                    WHERE _ingested_at >= '{cutoff_time}'
                """
                result = conn.execute(query).fetchone()
                count = result[0] if result else 0
                error_counts[table] = count
                total_errors += count

                print(f"DLQ table {table}: {count} errors in last 15 minutes")
            except Exception as e:
                print(f"Warning: Could not query {table}: {e}")
                error_counts[table] = 0

        conn.close()
    except Exception as e:
        print(f"Error connecting to DuckDB: {e}")
        print("DLQ tables may not exist yet - this is expected on first run")
        for table in DLQ_TABLES:
            error_counts[table] = 0

    context["ti"].xcom_push(key="error_counts", value=error_counts)
    context["ti"].xcom_push(key="total_errors", value=total_errors)

    print(f"Total DLQ errors: {total_errors}")
    return error_counts


def check_threshold(**context):
    """Check if error count exceeds threshold and branch accordingly."""
    total_errors = context["ti"].xcom_pull(task_ids="query_dlq_errors", key="total_errors")

    if total_errors is None:
        total_errors = 0

    print(f"Checking threshold: {total_errors} errors vs {ERROR_THRESHOLD} threshold")

    if total_errors > ERROR_THRESHOLD:
        return "send_alert"
    return "no_alert"


def send_alert(**context):
    """Send alert when error threshold is exceeded."""
    total_errors = context["ti"].xcom_pull(task_ids="query_dlq_errors", key="total_errors")
    error_counts = context["ti"].xcom_pull(task_ids="query_dlq_errors", key="error_counts")

    print("ALERT: DLQ errors exceeded threshold!")
    print(f"Total errors: {total_errors}")
    print("Error breakdown by table:")

    for table, count in error_counts.items():
        if count > 0:
            print(f"  - {table}: {count} errors")


with DAG(
    "dlq_monitoring",
    default_args=default_args,
    description="Monitor DLQ tables for errors every 15 minutes",
    schedule="3,18,33,48 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["monitoring", "dlq"],
) as dag:

    query_dlq_errors_task = PythonOperator(
        task_id="query_dlq_errors",
        python_callable=query_dlq_errors,
    )

    check_threshold_task = BranchPythonOperator(
        task_id="check_threshold",
        python_callable=check_threshold,
    )

    send_alert_task = PythonOperator(
        task_id="send_alert",
        python_callable=send_alert,
    )

    no_alert_task = EmptyOperator(
        task_id="no_alert",
    )

    query_dlq_errors_task >> check_threshold_task >> [send_alert_task, no_alert_task]
