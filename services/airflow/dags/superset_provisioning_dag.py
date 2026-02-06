"""Superset Dashboard Provisioning DAG.

Provisions Superset dashboards declaratively after Gold layer transformations.
Uses the new provisioning module for robust, idempotent dashboard creation.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk import Asset

# Asset definition for data lineage
SUPERSET_DASHBOARDS_ASSET = Asset("superset://dashboards/provisioned")

default_args = {
    "owner": "rideshare",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
}


def provision_dashboards(
    base_url: str = "http://superset:8088",
    force: bool = False,
    skip_table_check: bool = False,
) -> dict[str, object]:
    """Provision all Superset dashboards.

    Args:
        base_url: Superset base URL
        force: Recreate existing dashboards
        skip_table_check: Skip table existence verification

    Returns:
        Summary of provisioning results
    """
    import logging
    import sys

    # Add provisioning module to path (mounted in Airflow container)
    # analytics/superset is mounted at /opt/superset-provisioning
    sys.path.insert(0, "/opt/superset-provisioning")

    from provisioning.provisioner import ProvisioningStatus, provision_dashboards

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("Starting Superset dashboard provisioning...")
    logger.info("Base URL: %s, Force: %s, Skip table check: %s", base_url, force, skip_table_check)

    results = provision_dashboards(
        base_url=base_url,
        username="admin",
        password="admin",
        force=force,
        skip_table_check=skip_table_check,
        wait_for_healthy=True,
        health_timeout=120,
    )

    # Build summary with explicit types
    total = len(results)
    success_count = 0
    skipped_count = 0
    failed_count = 0
    dashboards_list: list[dict[str, object]] = []

    for result in results:
        if result.status == ProvisioningStatus.SUCCESS:
            success_count += 1
        elif result.status == ProvisioningStatus.SKIPPED:
            skipped_count += 1
        else:
            failed_count += 1

        dashboards_list.append(
            {
                "slug": result.dashboard_slug,
                "status": result.status.value,
                "dashboard_id": result.dashboard_id,
                "error": result.error,
            }
        )

    logger.info(
        "Provisioning complete: %d success, %d skipped, %d failed",
        success_count,
        skipped_count,
        failed_count,
    )

    # Fail the task if any dashboard failed OR if no dashboards were successfully created
    if failed_count > 0:
        failed_dashboards = [d["slug"] for d in dashboards_list if d["status"] == "failed"]
        raise RuntimeError(f"Dashboard provisioning failed for: {failed_dashboards}")

    if success_count == 0:
        raise RuntimeError(
            "No dashboards were successfully provisioned (all were skipped or failed)"
        )

    summary: dict[str, object] = {
        "total": total,
        "success": success_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "dashboards": dashboards_list,
    }

    return summary


def validate_dataset_queries(
    thrift_host: str = "spark-thrift-server",
    thrift_port: int = 10000,
) -> dict[str, object]:
    """Validate all dataset SQL queries against Spark Thrift Server.

    This task runs before dashboard provisioning to catch schema mismatches
    and missing data early.

    Args:
        thrift_host: Spark Thrift Server hostname
        thrift_port: Spark Thrift Server port

    Returns:
        Summary of validation results

    Raises:
        RuntimeError: If any critical validation failures occur
    """
    import logging
    import sys

    # Add provisioning module to path (mounted in Airflow container)
    # analytics/superset is mounted at /opt/superset-provisioning
    sys.path.insert(0, "/opt/superset-provisioning")

    from provisioning.validators import ValidationStatus, validate_datasets

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("Starting dataset SQL validation...")
    logger.info("Thrift Server: %s:%d", thrift_host, thrift_port)

    summary = validate_datasets(
        host=thrift_host,
        port=thrift_port,
    )

    # Build result summary with explicit types
    results_list: list[dict[str, object]] = []
    for result in summary.results:
        results_list.append(
            {
                "dataset": result.dataset_name,
                "status": result.status.value,
                "row_count": result.row_count,
                "error": result.error_message,
                "execution_time": result.execution_time,
            }
        )

    logger.info(
        "Validation complete: %d passed, %d warned, %d failed",
        summary.passed,
        summary.warned,
        summary.failed,
    )

    if summary.has_critical_failures:
        failed_datasets = [
            r.dataset_name for r in summary.results if r.status == ValidationStatus.FAIL
        ]
        raise RuntimeError(f"SQL validation failed for datasets: {failed_datasets}")

    result_summary: dict[str, object] = {
        "total": summary.total,
        "passed": summary.passed,
        "warned": summary.warned,
        "failed": summary.failed,
        "results": results_list,
    }

    return result_summary


with DAG(
    "superset_dashboard_provisioning",
    default_args=default_args,
    description="Provision Superset dashboards after Gold layer transformations",
    schedule=None,  # Triggered by Gold DAG
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["superset", "dashboards", "provisioning"],
) as dag:

    # Check Superset health before attempting provisioning
    check_superset_health = BashOperator(
        task_id="check_superset_health",
        bash_command="""
        echo "Checking Superset health..."
        for i in $(seq 1 30); do
            if curl -sf http://superset:8088/health > /dev/null; then
                echo "Superset is healthy"
                exit 0
            fi
            echo "Waiting for Superset... ($i/30)"
            sleep 10
        done
        echo "Superset health check failed"
        exit 1
        """,
        retries=2,
        retry_delay=timedelta(minutes=1),
    )

    # Validate dataset SQL queries against Spark Thrift Server
    validate_sql_task = PythonOperator(
        task_id="validate_dataset_queries",
        python_callable=validate_dataset_queries,
        op_kwargs={
            "thrift_host": "spark-thrift-server",
            "thrift_port": 10000,
        },
    )

    # Provision dashboards using the new module
    provision_dashboards_task = PythonOperator(
        task_id="provision_dashboards",
        python_callable=provision_dashboards,
        op_kwargs={
            "base_url": "http://superset:8088",
            "force": False,
            "skip_table_check": False,  # Verify tables exist in Gold layer
        },
        outlets=[SUPERSET_DASHBOARDS_ASSET],
    )

    # Log success
    log_success = BashOperator(
        task_id="log_success",
        bash_command='echo "Superset dashboards provisioned successfully at $(date)"',
    )

    check_superset_health >> validate_sql_task >> provision_dashboards_task >> log_success
