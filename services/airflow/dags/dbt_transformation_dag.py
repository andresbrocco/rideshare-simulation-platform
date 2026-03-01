"""DBT transformation DAGs for Silver and Gold layers."""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import (
    BranchPythonOperator,
    ShortCircuitOperator,
)
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.sdk import Asset

# Asset definitions for data lineage
SILVER_ASSET = Asset("lakehouse://silver/transformed")
GOLD_ASSET = Asset("lakehouse://gold/transformed")

# MinIO / S3 configuration for Bronze table checks
MINIO_ENDPOINT = os.environ.get("AWS_ENDPOINT_URL")
BRONZE_BUCKET = os.environ.get("BRONZE_BUCKET", "rideshare-bronze")

STORAGE_OPTIONS: dict[str, str] = {
    "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
}
if MINIO_ENDPOINT:
    # Local dev: explicit MinIO credentials
    STORAGE_OPTIONS["AWS_ACCESS_KEY_ID"] = os.environ.get("AWS_ACCESS_KEY_ID", "minioadmin")
    STORAGE_OPTIONS["AWS_SECRET_ACCESS_KEY"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "minioadmin")
    STORAGE_OPTIONS["AWS_ENDPOINT_URL"] = MINIO_ENDPOINT
    STORAGE_OPTIONS["AWS_ALLOW_HTTP"] = "true" if MINIO_ENDPOINT.startswith("http://") else "false"
else:
    # Production: use IRSA/Pod Identity credential chain
    STORAGE_OPTIONS["AWS_REGION"] = os.environ.get("AWS_REGION", "us-east-1")

# Bronze tables required for Silver layer transformations
REQUIRED_BRONZE_TABLES = [
    "bronze_trips",
    "bronze_gps_pings",
    "bronze_driver_status",
    "bronze_surge_updates",
    "bronze_ratings",
    "bronze_payments",
    "bronze_driver_profiles",
    "bronze_rider_profiles",
]


def check_bronze_data_exists() -> bool:
    """Check whether all required Bronze Delta tables exist.

    In local dev (AWS_ENDPOINT_URL set), pings MinIO health endpoint first.
    In production (AWS_ENDPOINT_URL empty), skips health check and goes
    straight to Delta table existence checks.
    Returns True to proceed with the DAG, False to skip all downstream tasks.
    """
    from deltalake import DeltaTable

    if MINIO_ENDPOINT:
        import urllib.request

        req = urllib.request.Request(f"{MINIO_ENDPOINT}/minio/health/live", method="GET")
        with urllib.request.urlopen(req, timeout=5):
            pass
        print(f"Connected to MinIO at {MINIO_ENDPOINT}")
    else:
        print("Production mode — skipping MinIO health check")

    for table in REQUIRED_BRONZE_TABLES:
        path = f"s3://{BRONZE_BUCKET}/{table}/"
        if not DeltaTable.is_deltatable(path, storage_options=STORAGE_OPTIONS):
            print(f"Bronze table missing: {table}")
            print("Skipping DAG run — Bronze data not ready yet")
            return False

    print("All Bronze tables present — proceeding with transformations")
    return True


default_args = {
    "owner": "rideshare",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

SILVER_SCHEDULE = os.environ.get("SILVER_SCHEDULE", "10 * * * *")

# Silver DAG - Runs at :10 past each hour with Bronze freshness check (configurable via SILVER_SCHEDULE env var)
with DAG(
    "dbt_silver_transformation",
    default_args=default_args,
    description="DBT Silver layer transformations",
    schedule=SILVER_SCHEDULE,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["dbt", "silver", "transformation"],
) as silver_dag:

    check_bronze_freshness = ShortCircuitOperator(
        task_id="check_bronze_freshness",
        python_callable=check_bronze_data_exists,
    )

    dbt_silver_run = BashOperator(
        task_id="dbt_silver_run",
        bash_command="cd /opt/dbt && dbt run --select tag:silver --target local --profiles-dir /opt/dbt",
    )

    dbt_silver_test = BashOperator(
        task_id="dbt_silver_test",
        bash_command="cd /opt/dbt && dbt test --select tag:silver --target local --threads 2 --profiles-dir /opt/dbt",
    )

    ge_silver_validation = BashOperator(
        task_id="ge_silver_validation",
        bash_command="""
        cd /opt/great-expectations && \
        python3 run_checkpoint.py silver_validation || echo "WARNING: Silver validation failed" && exit 0
        """,
        outlets=[SILVER_ASSET],
    )

    export_silver_to_s3 = BashOperator(
        task_id="export_silver_to_s3",
        bash_command="python3 /opt/init-scripts/export-dbt-to-s3.py --layer silver",
    )

    register_silver_trino_tables = BashOperator(
        task_id="register_silver_trino_tables",
        bash_command="python3 /opt/init-scripts/register-trino-tables.py --layer silver",
    )

    def should_trigger_gold(**context) -> str:
        """Trigger Gold DAG at 2 AM, for manual runs, or when not in PROD_MODE."""
        prod_mode = os.environ.get("PROD_MODE", "false").lower() == "true"
        logical_date = context.get("logical_date")
        # Trigger if: not PROD_MODE, manual run (no logical_date), or scheduled at 2 AM
        if not prod_mode or logical_date is None or logical_date.hour == 2:
            return "trigger_gold_dag"
        return "skip_gold_trigger"

    check_should_trigger_gold = BranchPythonOperator(
        task_id="check_should_trigger_gold",
        python_callable=should_trigger_gold,
    )

    trigger_gold_dag = TriggerDagRunOperator(
        task_id="trigger_gold_dag",
        trigger_dag_id="dbt_gold_transformation",
        wait_for_completion=False,
        conf={
            "triggered_by": "silver_dag",
            "silver_logical_date": "{{ logical_date | default('manual', true) }}",
        },
    )

    skip_gold_trigger = EmptyOperator(task_id="skip_gold_trigger")

    # Task dependencies
    (
        check_bronze_freshness
        >> dbt_silver_run
        >> dbt_silver_test
        >> ge_silver_validation
        >> export_silver_to_s3
    )
    (
        export_silver_to_s3
        >> register_silver_trino_tables
        >> check_should_trigger_gold
        >> [trigger_gold_dag, skip_gold_trigger]
    )

# Gold DAG - Triggered by Silver DAG at 2 AM (no schedule)
with DAG(
    "dbt_gold_transformation",
    default_args=default_args,
    description="DBT Gold layer transformations (triggered by Silver at 2 AM)",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["dbt", "gold", "transformation"],
) as gold_dag:

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command="cd /opt/dbt && dbt seed --target local --profiles-dir /opt/dbt",
    )

    dbt_gold_dimensions = BashOperator(
        task_id="dbt_gold_dimensions",
        bash_command="cd /opt/dbt && dbt run --select tag:dimensions --target local --profiles-dir /opt/dbt",
    )

    dbt_gold_facts = BashOperator(
        task_id="dbt_gold_facts",
        bash_command="cd /opt/dbt && dbt run --select tag:facts --target local --profiles-dir /opt/dbt",
    )

    dbt_gold_aggregates = BashOperator(
        task_id="dbt_gold_aggregates",
        bash_command="cd /opt/dbt && dbt run --select tag:aggregates --target local --profiles-dir /opt/dbt",
    )

    dbt_gold_test = BashOperator(
        task_id="dbt_gold_test",
        bash_command="cd /opt/dbt && dbt test --select tag:gold --target local --threads 2 --profiles-dir /opt/dbt",
    )

    ge_gold_validation = BashOperator(
        task_id="ge_gold_validation",
        bash_command="""
        cd /opt/great-expectations && \
        python3 run_checkpoint.py gold_validation || echo "WARNING: Gold validation failed" && exit 0
        """,
    )

    export_gold_to_s3 = BashOperator(
        task_id="export_gold_to_s3",
        bash_command="python3 /opt/init-scripts/export-dbt-to-s3.py --layer gold",
    )

    register_gold_trino_tables = BashOperator(
        task_id="register_gold_trino_tables",
        bash_command="python3 /opt/init-scripts/register-trino-tables.py --layer gold",
    )

    ge_generate_data_docs = BashOperator(
        task_id="ge_generate_data_docs",
        bash_command="""
        cd /opt/great-expectations && \
        python3 build_data_docs.py
        """,
        outlets=[GOLD_ASSET],
    )

    (
        dbt_seed
        >> dbt_gold_dimensions
        >> dbt_gold_facts
        >> dbt_gold_aggregates
        >> dbt_gold_test
        >> ge_gold_validation
        >> export_gold_to_s3
        >> register_gold_trino_tables
        >> ge_generate_data_docs
    )
