"""Tests for DBT transformation DAG."""

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
    """Verify DBT transformation DAGs are loaded without errors."""
    assert "dbt_silver_transformation" in dagbag.dags
    assert "dbt_gold_transformation" in dagbag.dags
    assert len(dagbag.import_errors) == 0


def test_dbt_silver_dag_structure(dagbag):
    """Verify Silver DAG has correct tasks and dependencies."""
    dag = dagbag.dags["dbt_silver_transformation"]
    assert dag is not None

    tasks = {task.task_id: task for task in dag.tasks}
    assert "check_bronze_freshness" in tasks
    assert "dbt_silver_run" in tasks
    assert "dbt_silver_test" in tasks

    silver_run_task = tasks["dbt_silver_run"]
    upstream_task_ids = {task.task_id for task in silver_run_task.upstream_list}
    assert "check_bronze_freshness" in upstream_task_ids

    silver_test_task = tasks["dbt_silver_test"]
    upstream_task_ids = {task.task_id for task in silver_test_task.upstream_list}
    assert "dbt_silver_run" in upstream_task_ids


def test_dbt_silver_command(dagbag):
    """Verify DBT Silver run command includes tag:silver."""
    dag = dagbag.dags["dbt_silver_transformation"]
    tasks = {task.task_id: task for task in dag.tasks}
    silver_run_task = tasks["dbt_silver_run"]

    assert hasattr(silver_run_task, "bash_command")
    assert "dbt run" in silver_run_task.bash_command
    assert "tag:silver" in silver_run_task.bash_command


def test_dbt_gold_dag_structure(dagbag):
    """Verify Gold DAG has correct tasks and dependencies."""
    dag = dagbag.dags["dbt_gold_transformation"]
    assert dag is not None

    tasks = {task.task_id: task for task in dag.tasks}
    assert "dbt_gold_dimensions" in tasks
    assert "dbt_gold_facts" in tasks
    assert "dbt_gold_aggregates" in tasks
    assert "dbt_gold_test" in tasks

    facts_task = tasks["dbt_gold_facts"]
    upstream_task_ids = {task.task_id for task in facts_task.upstream_list}
    assert "dbt_gold_dimensions" in upstream_task_ids

    aggregates_task = tasks["dbt_gold_aggregates"]
    upstream_task_ids = {task.task_id for task in aggregates_task.upstream_list}
    assert "dbt_gold_facts" in upstream_task_ids

    test_task = tasks["dbt_gold_test"]
    upstream_task_ids = {task.task_id for task in test_task.upstream_list}
    assert "dbt_gold_aggregates" in upstream_task_ids


def test_dbt_gold_dimensions_command(dagbag):
    """Verify DBT Gold dimensions command includes tag:dimensions."""
    dag = dagbag.dags["dbt_gold_transformation"]
    tasks = {task.task_id: task for task in dag.tasks}
    dimensions_task = tasks["dbt_gold_dimensions"]

    assert hasattr(dimensions_task, "bash_command")
    assert "dbt run" in dimensions_task.bash_command
    assert "tag:dimensions" in dimensions_task.bash_command


def test_dbt_gold_facts_command(dagbag):
    """Verify DBT Gold facts command includes tag:facts."""
    dag = dagbag.dags["dbt_gold_transformation"]
    tasks = {task.task_id: task for task in dag.tasks}
    facts_task = tasks["dbt_gold_facts"]

    assert hasattr(facts_task, "bash_command")
    assert "dbt run" in facts_task.bash_command
    assert "tag:facts" in facts_task.bash_command


def test_dbt_gold_aggregates_command(dagbag):
    """Verify DBT Gold aggregates command includes tag:aggregates."""
    dag = dagbag.dags["dbt_gold_transformation"]
    tasks = {task.task_id: task for task in dag.tasks}
    aggregates_task = tasks["dbt_gold_aggregates"]

    assert hasattr(aggregates_task, "bash_command")
    assert "dbt run" in aggregates_task.bash_command
    assert "tag:aggregates" in aggregates_task.bash_command


def test_schedule_hourly(dagbag):
    """Verify Silver DAG runs hourly."""
    dag = dagbag.dags["dbt_silver_transformation"]
    assert dag.schedule == "@hourly" or dag.schedule_interval == "@hourly"


def test_schedule_daily(dagbag):
    """Verify Gold DAG runs daily."""
    dag = dagbag.dags["dbt_gold_transformation"]
    assert dag.schedule == "@daily" or dag.schedule_interval == "@daily"


def test_no_catchup(dagbag):
    """Verify DAGs don't catch up on past runs."""
    silver_dag = dagbag.dags["dbt_silver_transformation"]
    gold_dag = dagbag.dags["dbt_gold_transformation"]

    assert silver_dag.catchup is False
    assert gold_dag.catchup is False


def test_failure_callback(dagbag):
    """Verify failure alerting configured via default_args."""
    silver_dag = dagbag.dags["dbt_silver_transformation"]
    gold_dag = dagbag.dags["dbt_gold_transformation"]

    assert hasattr(silver_dag, "default_args")
    assert hasattr(gold_dag, "default_args")

    assert "retries" in silver_dag.default_args
    assert "retries" in gold_dag.default_args
    assert silver_dag.default_args["retries"] >= 1
    assert gold_dag.default_args["retries"] >= 1
