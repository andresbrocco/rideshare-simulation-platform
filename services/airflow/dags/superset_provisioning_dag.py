"""Superset dashboard provisioning DAG triggered after Gold transformation."""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import Asset

DASHBOARDS_ASSET = Asset("superset://dashboards/provisioned")

default_args = {
    "owner": "rideshare",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def check_superset_health(**context: object) -> bool:
    """Check if Superset is healthy before provisioning."""
    import time

    import requests

    for i in range(5):
        try:
            response = requests.get("http://superset:8088/health", timeout=10)
            if response.status_code == 200:
                print("Superset is healthy")
                return True
        except requests.exceptions.RequestException as e:
            print(f"Health check attempt {i + 1}/5 failed: {e}")
        time.sleep(5)

    print("WARNING: Superset not reachable, provisioning may fail")
    return False


with DAG(
    "superset_dashboard_provisioning",
    default_args=default_args,
    description="Provision Superset dashboards after Gold layer is ready",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["superset", "dashboards", "provisioning"],
) as dag:

    check_superset = PythonOperator(
        task_id="check_superset_health",
        python_callable=check_superset_health,
    )

    provision_dashboards = BashOperator(
        task_id="provision_dashboards",
        bash_command="""
        cd /opt/superset-dashboards && \
        python3 provision_dashboards.py --base-url http://superset:8088 \
        || echo "WARNING: Dashboard provisioning encountered errors"
        """,
        env={
            "SUPERSET_ADMIN_USERNAME": "admin",
            "SUPERSET_ADMIN_PASSWORD": "admin",
        },
        outlets=[DASHBOARDS_ASSET],
    )

    check_superset >> provision_dashboards
