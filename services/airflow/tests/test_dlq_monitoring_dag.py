"""Tests for DLQ monitoring DAG."""

import pytest
from airflow.models import DagBag


@pytest.fixture
def dagbag():
    """Load DAGs from the dags folder."""
    return DagBag(
        dag_folder="/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/airflow/dags/",
        include_examples=False,
    )


def test_dag_loaded(dagbag):
    """Verify DLQ monitoring DAG is loaded without errors."""
    assert "dlq_monitoring" in dagbag.dags
    assert len(dagbag.import_errors) == 0


def test_dag_structure(dagbag):
    """Verify DAG has monitoring tasks."""
    dag = dagbag.dags["dlq_monitoring"]
    assert dag is not None

    tasks = {task.task_id for task in dag.tasks}
    assert "query_dlq_errors" in tasks
    assert "check_threshold" in tasks
    assert "send_alert" in tasks
    assert "no_alert" in tasks


def test_schedule_15_minutes_offset(dagbag):
    """Verify DAG runs every 15 minutes with 3-minute offset."""
    dag = dagbag.dags["dlq_monitoring"]
    schedule = getattr(dag, "schedule_interval", None) or dag.schedule
    assert schedule == "3,18,33,48 * * * *"


def test_no_catchup(dagbag):
    """Verify DAG doesn't catch up on past runs."""
    dag = dagbag.dags["dlq_monitoring"]
    assert dag.catchup is False


def test_task_dependencies(dagbag):
    """Verify task dependencies are correctly configured."""
    dag = dagbag.dags["dlq_monitoring"]
    tasks = {task.task_id: task for task in dag.tasks}

    query_task = tasks["query_dlq_errors"]
    check_task = tasks["check_threshold"]
    alert_task = tasks["send_alert"]
    no_alert_task = tasks["no_alert"]

    # Check that query_dlq_errors runs first
    query_downstream = {task.task_id for task in query_task.downstream_list}
    assert "check_threshold" in query_downstream

    # Check that check_threshold branches to alert or no_alert
    check_downstream = {task.task_id for task in check_task.downstream_list}
    assert "send_alert" in check_downstream
    assert "no_alert" in check_downstream

    # Check that alert tasks have check_threshold as upstream
    alert_upstream = {task.task_id for task in alert_task.upstream_list}
    assert "check_threshold" in alert_upstream

    no_alert_upstream = {task.task_id for task in no_alert_task.upstream_list}
    assert "check_threshold" in no_alert_upstream


def test_query_task_is_python_operator(dagbag):
    """Verify query task uses PythonOperator."""
    dag = dagbag.dags["dlq_monitoring"]
    tasks = {task.task_id: task for task in dag.tasks}
    query_task = tasks["query_dlq_errors"]

    assert query_task.task_type == "PythonOperator"
    assert hasattr(query_task, "python_callable")


def test_check_threshold_is_branch_operator(dagbag):
    """Verify threshold check uses BranchPythonOperator."""
    dag = dagbag.dags["dlq_monitoring"]
    tasks = {task.task_id: task for task in dag.tasks}
    check_task = tasks["check_threshold"]

    assert check_task.task_type == "BranchPythonOperator"
    assert hasattr(check_task, "python_callable")


def test_alert_task_is_python_operator(dagbag):
    """Verify alert task uses PythonOperator."""
    dag = dagbag.dags["dlq_monitoring"]
    tasks = {task.task_id: task for task in dag.tasks}
    alert_task = tasks["send_alert"]

    assert alert_task.task_type == "PythonOperator"
    assert hasattr(alert_task, "python_callable")


def test_no_alert_is_empty_operator(dagbag):
    """Verify no_alert task uses EmptyOperator."""
    dag = dagbag.dags["dlq_monitoring"]
    tasks = {task.task_id: task for task in dag.tasks}
    no_alert_task = tasks["no_alert"]

    assert no_alert_task.task_type == "EmptyOperator"


def test_default_args_configured(dagbag):
    """Verify DAG has default_args with retries."""
    dag = dagbag.dags["dlq_monitoring"]

    assert hasattr(dag, "default_args")
    assert "retries" in dag.default_args
    assert dag.default_args["retries"] >= 1


def test_dag_tags(dagbag):
    """Verify DAG has appropriate tags."""
    dag = dagbag.dags["dlq_monitoring"]

    assert hasattr(dag, "tags")
    assert "monitoring" in dag.tags or "dlq" in dag.tags
