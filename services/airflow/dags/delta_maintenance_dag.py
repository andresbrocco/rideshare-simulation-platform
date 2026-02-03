"""Delta Lake maintenance DAG for OPTIMIZE and VACUUM operations.

This DAG performs daily maintenance on Bronze Delta tables to:
1. OPTIMIZE: Compact small files into larger ones for better read performance
2. VACUUM: Remove old files no longer referenced by the Delta log

Schedule: 3 AM daily (after Gold DAG completes at 2 AM)
"""

from datetime import datetime, timedelta
from typing import Any

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.operators.empty import EmptyOperator

# Bronze tables to maintain
BRONZE_TABLES = [
    "bronze_trips",
    "bronze_gps_pings",
    "bronze_driver_status",
    "bronze_surge_updates",
    "bronze_ratings",
    "bronze_payments",
    "bronze_driver_profiles",
    "bronze_rider_profiles",
]

# DLQ tables (one per Bronze table)
DLQ_TABLES = [f"dlq_{t.replace('bronze_', '')}" for t in BRONZE_TABLES]

# All tables to maintain
ALL_TABLES = BRONZE_TABLES + DLQ_TABLES

# VACUUM retention in hours (7 days)
VACUUM_RETENTION_HOURS = 168


def optimize_table(table_name: str, **context: Any) -> dict[str, object]:
    """Run OPTIMIZE on a Delta table.

    Args:
        table_name: Name of the table to optimize.
        **context: Airflow context.

    Returns:
        Dictionary with table name and operation status.
    """
    from pyhive import hive

    conn = hive.connect(host="spark-thrift-server", port=10000, auth="NOSASL")
    cursor = conn.cursor()
    try:
        cursor.execute(f"OPTIMIZE bronze.{table_name}")
        return {"table": table_name, "status": "success", "operation": "OPTIMIZE"}
    except Exception as e:
        return {"table": table_name, "status": "failed", "error": str(e), "operation": "OPTIMIZE"}
    finally:
        cursor.close()
        conn.close()


def vacuum_table(
    table_name: str, retention_hours: int = VACUUM_RETENTION_HOURS, **context: Any
) -> dict[str, object]:
    """Run VACUUM on a Delta table.

    Args:
        table_name: Name of the table to vacuum.
        retention_hours: Hours of history to retain.
        **context: Airflow context.

    Returns:
        Dictionary with table name and operation status.
    """
    from pyhive import hive

    conn = hive.connect(host="spark-thrift-server", port=10000, auth="NOSASL")
    cursor = conn.cursor()
    try:
        cursor.execute(f"VACUUM bronze.{table_name} RETAIN {retention_hours} HOURS")
        return {"table": table_name, "status": "success", "operation": "VACUUM"}
    except Exception as e:
        return {"table": table_name, "status": "failed", "error": str(e), "operation": "VACUUM"}
    finally:
        cursor.close()
        conn.close()


def summarize_results(**context: Any) -> dict[str, Any]:
    """Summarize OPTIMIZE and VACUUM results from all tasks.

    Args:
        **context: Airflow context containing task instance.

    Returns:
        Dictionary with summary of all operations.
    """
    ti = context["ti"]
    results: dict[str, list[dict[str, object]]] = {"optimize": [], "vacuum": []}

    for table in ALL_TABLES:
        optimize_result = ti.xcom_pull(task_ids=f"optimize_{table}")
        vacuum_result = ti.xcom_pull(task_ids=f"vacuum_{table}")

        if optimize_result:
            results["optimize"].append(optimize_result)
        if vacuum_result:
            results["vacuum"].append(vacuum_result)

    # Count successes and failures
    optimize_success = sum(1 for r in results["optimize"] if r.get("status") == "success")
    optimize_failed = len(results["optimize"]) - optimize_success
    vacuum_success = sum(1 for r in results["vacuum"] if r.get("status") == "success")
    vacuum_failed = len(results["vacuum"]) - vacuum_success

    summary = {
        "total_tables": len(ALL_TABLES),
        "optimize_success": optimize_success,
        "optimize_failed": optimize_failed,
        "vacuum_success": vacuum_success,
        "vacuum_failed": vacuum_failed,
    }

    print(f"Delta Maintenance Summary: {summary}")
    return summary


default_args = {
    "owner": "rideshare",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "delta_maintenance",
    default_args=default_args,
    description="Daily OPTIMIZE and VACUUM for Bronze Delta tables",
    schedule="0 3 * * *",  # 3 AM daily
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_tasks=4,  # Limit parallel operations
    tags=["delta", "maintenance", "bronze"],
) as dag:

    start = EmptyOperator(task_id="start")

    # Create OPTIMIZE tasks for all tables
    optimize_tasks = []
    for table in ALL_TABLES:
        task = PythonOperator(
            task_id=f"optimize_{table}",
            python_callable=optimize_table,
            op_kwargs={"table_name": table},
        )
        start >> task
        optimize_tasks.append(task)

    # Barrier between OPTIMIZE and VACUUM
    optimize_complete = EmptyOperator(task_id="optimize_complete")
    for task in optimize_tasks:
        task >> optimize_complete

    # Create VACUUM tasks for all tables
    vacuum_tasks = []
    for table in ALL_TABLES:
        task = PythonOperator(
            task_id=f"vacuum_{table}",
            python_callable=vacuum_table,
            op_kwargs={"table_name": table, "retention_hours": VACUUM_RETENTION_HOURS},
        )
        optimize_complete >> task
        vacuum_tasks.append(task)

    # Barrier after VACUUM
    vacuum_complete = EmptyOperator(task_id="vacuum_complete")
    for task in vacuum_tasks:
        task >> vacuum_complete

    # Summarize results
    summarize = PythonOperator(
        task_id="summarize",
        python_callable=summarize_results,
    )

    vacuum_complete >> summarize
