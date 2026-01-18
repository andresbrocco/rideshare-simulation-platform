"""Bronze Layer Initialization DAG.

Initializes the Bronze database and tables in Hive metastore on first deployment.
This DAG should be run once manually after the data platform is deployed.
"""

from datetime import datetime
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator


def initialize_bronze_metastore():
    """Run the Bronze metastore initialization script."""
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "/opt/init-scripts/init-bronze-metastore.py",
        ],
        capture_output=True,
        text=True,
    )

    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        raise Exception(f"Initialization failed with code {result.returncode}")


default_args = {
    "owner": "rideshare",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
}

with DAG(
    dag_id="bronze_initialization",
    default_args=default_args,
    description="Initialize Bronze database and tables in Hive metastore (run once)",
    schedule=None,  # Manual trigger only
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["bronze", "initialization", "one-time"],
) as dag:

    init_task = PythonOperator(
        task_id="initialize_bronze_metastore",
        python_callable=initialize_bronze_metastore,
    )
