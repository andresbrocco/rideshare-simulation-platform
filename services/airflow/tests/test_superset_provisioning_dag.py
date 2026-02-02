"""Tests for Superset dashboard provisioning DAG."""

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
    """Verify Superset provisioning DAG is loaded without errors."""
    assert "superset_dashboard_provisioning" in dagbag.dags
    assert len(dagbag.import_errors) == 0


def test_superset_dag_structure(dagbag):
    """Verify Superset DAG has correct tasks."""
    dag = dagbag.dags["superset_dashboard_provisioning"]
    assert dag is not None

    task_ids = {task.task_id for task in dag.tasks}
    assert "check_superset_health" in task_ids
    assert "provision_dashboards" in task_ids


def test_superset_dag_task_dependencies(dagbag):
    """Verify task dependencies are correct."""
    dag = dagbag.dags["superset_dashboard_provisioning"]
    tasks = {task.task_id: task for task in dag.tasks}

    provision_task = tasks["provision_dashboards"]
    upstream_task_ids = {task.task_id for task in provision_task.upstream_list}
    assert "check_superset_health" in upstream_task_ids


def test_superset_dag_schedule_none(dagbag):
    """Verify DAG has no schedule (triggered by Gold DAG)."""
    dag = dagbag.dags["superset_dashboard_provisioning"]
    schedule = getattr(dag, "schedule_interval", None) or dag.schedule
    assert schedule is None


def test_superset_dag_no_catchup(dagbag):
    """Verify DAG doesn't catch up on past runs."""
    dag = dagbag.dags["superset_dashboard_provisioning"]
    assert dag.catchup is False


def test_superset_dag_tags(dagbag):
    """Verify DAG has appropriate tags."""
    dag = dagbag.dags["superset_dashboard_provisioning"]
    assert "superset" in dag.tags
    assert "dashboards" in dag.tags


def test_provision_dashboards_has_outlet(dagbag):
    """Verify provision_dashboards has DASHBOARDS_ASSET outlet."""
    dag = dagbag.dags["superset_dashboard_provisioning"]
    tasks = {task.task_id: task for task in dag.tasks}
    assert len(tasks["provision_dashboards"].outlets) > 0


def test_gold_dag_has_superset_trigger(dagbag):
    """Verify Gold DAG triggers Superset provisioning."""
    dag = dagbag.dags["dbt_gold_transformation"]
    task_ids = {task.task_id for task in dag.tasks}
    assert "trigger_superset_provisioning" in task_ids


def test_gold_dag_superset_trigger_config(dagbag):
    """Verify TriggerDagRunOperator configuration for Superset."""
    dag = dagbag.dags["dbt_gold_transformation"]
    tasks = {task.task_id: task for task in dag.tasks}
    trigger_task = tasks["trigger_superset_provisioning"]
    assert trigger_task.trigger_dag_id == "superset_dashboard_provisioning"
    assert trigger_task.wait_for_completion is False


def test_gold_dag_superset_trigger_dependency(dagbag):
    """Verify Superset trigger follows ge_generate_data_docs."""
    dag = dagbag.dags["dbt_gold_transformation"]
    tasks = {task.task_id: task for task in dag.tasks}

    trigger_task = tasks["trigger_superset_provisioning"]
    upstream_task_ids = {task.task_id for task in trigger_task.upstream_list}
    assert "ge_generate_data_docs" in upstream_task_ids
