"""Streaming Jobs Lifecycle DAG - DEPRECATED.

⚠️  This DAG is DEPRECATED as of 2026-01-18.

Streaming jobs are now managed as dedicated docker-compose services with
automatic restart capabilities. This DAG is kept for reference only.

See: infrastructure/docker/compose.yml (spark-streaming-* services)
"""

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.sensors.python import PythonSensor
from airflow.task.trigger_rule import TriggerRule

# Environment detection
ENVIRONMENT = os.getenv("RIDESHARE_ENVIRONMENT", "local")
IS_LOCAL = ENVIRONMENT == "local"

# Try to import Databricks operator, use stub if not available
try:
    from airflow.providers.databricks.operators.databricks import (
        DatabricksSubmitRunOperator,
    )

    DATABRICKS_AVAILABLE = True
except ImportError:
    DATABRICKS_AVAILABLE = False

    # Create a stub operator for testing when Databricks provider is not installed
    class DatabricksSubmitRunOperator(PythonOperator):
        """Stub operator used when Databricks provider is not installed."""

        def __init__(
            self,
            databricks_conn_id=None,
            new_cluster=None,
            spark_python_task=None,
            run_name=None,
            **kwargs,
        ):
            super().__init__(
                python_callable=lambda: print(f"Databricks job: {run_name}"), **kwargs
            )


# Streaming job configurations (consolidated as of 2026-01-26)
# - high_volume: handles gps-pings topic (high throughput, needs isolation)
# - low_volume: handles 7 other topics (trips, driver-status, surge-updates, etc.)
STREAMING_JOBS = [
    {"name": "high_volume", "file": "high_volume_streaming_job.py"},
    {"name": "low_volume", "file": "low_volume_streaming_job.py"},
]

default_args = {
    "owner": "rideshare",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
}


def check_job_running(job_name: str) -> bool:
    """Check if a streaming job is already running in Spark cluster."""
    import requests

    try:
        # Check Spark Master for running applications
        response = requests.get("http://spark-master:8080/json/", timeout=5)
        data = response.json()

        # Look for application with matching name
        for app in data.get("activeapps", []):
            if job_name.lower() in app.get("name", "").lower():
                return True

        return False
    except Exception as e:
        print(f"Error checking job status: {e}")
        return False


def submit_streaming_job_if_not_running(job_name: str, job_file: str) -> str:
    """Submit streaming job only if it's not already running (idempotent)."""
    import subprocess

    # Check if job is already running
    if check_job_running(job_name):
        return f"Job {job_name} is already running - skipping submission"

    # Build spark-submit command
    cmd = [
        "docker",
        "exec",
        "-d",
        "rideshare-spark-master",
        "bash",
        "-c",
        f"""nohup /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --name "streaming_{job_name}" \
  --conf spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension \
  --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog \
  --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
  --conf spark.hadoop.fs.s3a.access.key=minioadmin \
  --conf spark.hadoop.fs.s3a.secret.key=minioadmin \
  --conf spark.hadoop.fs.s3a.path.style.access=true \
  /opt/spark_streaming/jobs/{job_file} > /tmp/{job_name}_job.log 2>&1 &""",
    ]

    # Submit job
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        return f"Submitted job {job_name} successfully"
    else:
        raise Exception(f"Failed to submit job {job_name}: {result.stderr}")


with DAG(
    dag_id="streaming_jobs_lifecycle",
    default_args=default_args,
    description="Manages Spark Structured Streaming jobs for Bronze layer ingestion",
    schedule=None,  # CHANGED from timedelta(minutes=5) - DEPRECATED
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["streaming", "monitoring"],
    params={},
) as dag:

    submit_tasks = []
    health_tasks = []

    for job in STREAMING_JOBS:
        # Create idempotent submit task
        if IS_LOCAL:
            submit_task = PythonOperator(
                task_id=f"submit_{job['name']}",
                python_callable=submit_streaming_job_if_not_running,
                op_kwargs={"job_name": job["name"], "job_file": job["file"]},
            )
        else:
            submit_task = DatabricksSubmitRunOperator(
                task_id=f"submit_{job['name']}",
                databricks_conn_id="databricks_default",
                new_cluster={
                    "spark_version": "14.3.x-scala2.12",
                    "node_type_id": "i3.xlarge",
                    "num_workers": 1,
                },
                spark_python_task={
                    "python_file": f"dbfs:/streaming_jobs/{job['file']}",
                },
                run_name=f"streaming_{job['name']}",
            )

        # Health check sensor
        health_task = PythonSensor(
            task_id=f"health_check_{job['name']}",
            python_callable=check_job_running,
            op_kwargs={"job_name": job["name"]},
            timeout=300,
            poke_interval=60,
        )

        # Set dependencies
        submit_task >> health_task

        submit_tasks.append(submit_task)
        health_tasks.append(health_task)

    # Restart failed jobs task
    restart_failed_jobs = PythonOperator(
        task_id="restart_failed_jobs",
        python_callable=lambda: print("Restarting failed jobs"),
        trigger_rule=TriggerRule.ONE_FAILED,
    )

    # Connect all health checks to restart task
    for health_task in health_tasks:
        health_task >> restart_failed_jobs
