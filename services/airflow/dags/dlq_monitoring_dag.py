"""DLQ monitoring DAG that checks error counts every 15 minutes."""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.standard.operators.python import (
    PythonOperator,
    BranchPythonOperator,
)
from airflow.providers.standard.operators.empty import EmptyOperator

ERROR_THRESHOLD = 10

DLQ_TABLES = [
    "dlq_trips",
    "dlq_gps_pings",
    "dlq_driver_status",
    "dlq_surge_updates",
    "dlq_ratings",
    "dlq_payments",
    "dlq_driver_profiles",
    "dlq_rider_profiles",
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
    """Query all DLQ tables for error counts in the last 15 minutes."""
    from pyspark.sql import SparkSession
    from datetime import datetime, timedelta

    spark = (
        SparkSession.builder.appName("DLQ Monitoring")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin")
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )

    error_counts = {}
    total_errors = 0
    cutoff_time = datetime.now() - timedelta(minutes=15)

    for table in DLQ_TABLES:
        try:
            dlq_path = f"s3a://rideshare-bronze/{table}/"
            df = spark.read.format("delta").load(dlq_path)

            count = df.filter(df._ingested_at >= cutoff_time).count()
            error_counts[table] = count
            total_errors += count

            print(f"DLQ table {table}: {count} errors in last 15 minutes")
        except Exception as e:
            print(f"Warning: Could not query {table}: {e}")
            error_counts[table] = 0

    spark.stop()

    context["ti"].xcom_push(key="error_counts", value=error_counts)
    context["ti"].xcom_push(key="total_errors", value=total_errors)

    print(f"Total DLQ errors: {total_errors}")
    return error_counts


def check_threshold(**context):
    """Check if error count exceeds threshold and branch accordingly."""
    total_errors = context["ti"].xcom_pull(
        task_ids="query_dlq_errors", key="total_errors"
    )

    if total_errors is None:
        total_errors = 0

    print(f"Checking threshold: {total_errors} errors vs {ERROR_THRESHOLD} threshold")

    if total_errors > ERROR_THRESHOLD:
        return "send_alert"
    return "no_alert"


def send_alert(**context):
    """Send alert when error threshold is exceeded."""
    total_errors = context["ti"].xcom_pull(
        task_ids="query_dlq_errors", key="total_errors"
    )
    error_counts = context["ti"].xcom_pull(
        task_ids="query_dlq_errors", key="error_counts"
    )

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
    schedule=timedelta(minutes=15),
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
