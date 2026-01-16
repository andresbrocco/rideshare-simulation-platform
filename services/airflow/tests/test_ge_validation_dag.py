"""Tests for Great Expectations validation tasks in DBT transformation DAGs."""

import pytest
from airflow.models import DagBag


@pytest.fixture
def dagbag():
    """Load DAGs from the dags folder."""
    return DagBag(
        dag_folder="/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/airflow/dags/",
        include_examples=False,
    )


def test_dag_structure(dagbag):
    """Verify DAG has correct validation tasks."""
    silver_dag = dagbag.dags["dbt_transformation"]
    gold_dag = dagbag.dags["dbt_gold_transformation"]

    silver_tasks = {task.task_id for task in silver_dag.tasks}
    assert "ge_silver_validation" in silver_tasks

    gold_tasks = {task.task_id for task in gold_dag.tasks}
    assert "ge_gold_validation" in gold_tasks
    assert "ge_generate_data_docs" in gold_tasks


def test_soft_failure_handling(dagbag):
    """Verify validation failures don't block pipeline."""
    silver_dag = dagbag.dags["dbt_transformation"]
    gold_dag = dagbag.dags["dbt_gold_transformation"]

    silver_tasks = {task.task_id: task for task in silver_dag.tasks}
    silver_validation = silver_tasks["ge_silver_validation"]

    assert hasattr(silver_validation, "bash_command")
    assert "exit 0" in silver_validation.bash_command
    assert (
        "WARNING" in silver_validation.bash_command
        or "echo" in silver_validation.bash_command
    )

    gold_tasks = {task.task_id: task for task in gold_dag.tasks}
    gold_validation = gold_tasks["ge_gold_validation"]

    assert hasattr(gold_validation, "bash_command")
    assert "exit 0" in gold_validation.bash_command
    assert (
        "WARNING" in gold_validation.bash_command
        or "echo" in gold_validation.bash_command
    )


def test_task_dependencies(dagbag):
    """Verify GE validation runs after DBT."""
    silver_dag = dagbag.dags["dbt_transformation"]
    silver_tasks = {task.task_id: task for task in silver_dag.tasks}
    silver_validation = silver_tasks["ge_silver_validation"]

    upstream_task_ids = {task.task_id for task in silver_validation.upstream_list}
    assert "dbt_silver_test" in upstream_task_ids

    gold_dag = dagbag.dags["dbt_gold_transformation"]
    gold_tasks = {task.task_id: task for task in gold_dag.tasks}
    gold_validation = gold_tasks["ge_gold_validation"]

    upstream_task_ids = {task.task_id for task in gold_validation.upstream_list}
    assert "dbt_gold_test" in upstream_task_ids


def test_silver_validation_command(dagbag):
    """Verify Silver validation task runs correct checkpoint."""
    silver_dag = dagbag.dags["dbt_transformation"]
    silver_tasks = {task.task_id: task for task in silver_dag.tasks}
    silver_validation = silver_tasks["ge_silver_validation"]

    assert hasattr(silver_validation, "bash_command")
    assert "run_checkpoint.py" in silver_validation.bash_command
    assert "silver_validation" in silver_validation.bash_command


def test_gold_validation_command(dagbag):
    """Verify Gold validation task runs correct checkpoint."""
    gold_dag = dagbag.dags["dbt_gold_transformation"]
    gold_tasks = {task.task_id: task for task in gold_dag.tasks}
    gold_validation = gold_tasks["ge_gold_validation"]

    assert hasattr(gold_validation, "bash_command")
    assert "run_checkpoint.py" in gold_validation.bash_command
    assert "gold_validation" in gold_validation.bash_command


def test_data_docs_generation(dagbag):
    """Verify data docs generation task exists and runs after validation."""
    gold_dag = dagbag.dags["dbt_gold_transformation"]
    gold_tasks = {task.task_id: task for task in gold_dag.tasks}

    assert "ge_generate_data_docs" in gold_tasks
    data_docs_task = gold_tasks["ge_generate_data_docs"]

    assert hasattr(data_docs_task, "bash_command")
    assert "build_data_docs.py" in data_docs_task.bash_command

    upstream_task_ids = {task.task_id for task in data_docs_task.upstream_list}
    assert "ge_gold_validation" in upstream_task_ids


def test_ge_working_directory(dagbag):
    """Verify GE tasks run in correct directory."""
    silver_dag = dagbag.dags["dbt_transformation"]
    gold_dag = dagbag.dags["dbt_gold_transformation"]

    silver_tasks = {task.task_id: task for task in silver_dag.tasks}
    silver_validation = silver_tasks["ge_silver_validation"]
    assert "cd /opt/great-expectations" in silver_validation.bash_command

    gold_tasks = {task.task_id: task for task in gold_dag.tasks}
    gold_validation = gold_tasks["ge_gold_validation"]
    data_docs_task = gold_tasks["ge_generate_data_docs"]

    assert "cd /opt/great-expectations" in gold_validation.bash_command
    assert "cd /opt/great-expectations" in data_docs_task.bash_command


def test_silver_dag_full_pipeline(dagbag):
    """Verify complete Silver pipeline flow."""
    silver_dag = dagbag.dags["dbt_transformation"]
    silver_tasks = {task.task_id: task for task in silver_dag.tasks}

    # Verify all required tasks exist
    assert "check_bronze_freshness" in silver_tasks
    silver_run = silver_tasks["dbt_silver_run"]
    silver_test = silver_tasks["dbt_silver_test"]
    silver_validation = silver_tasks["ge_silver_validation"]

    silver_run_upstream = {task.task_id for task in silver_run.upstream_list}
    assert "check_bronze_freshness" in silver_run_upstream

    silver_test_upstream = {task.task_id for task in silver_test.upstream_list}
    assert "dbt_silver_run" in silver_test_upstream

    validation_upstream = {task.task_id for task in silver_validation.upstream_list}
    assert "dbt_silver_test" in validation_upstream


def test_gold_dag_full_pipeline(dagbag):
    """Verify complete Gold pipeline flow."""
    gold_dag = dagbag.dags["dbt_gold_transformation"]
    gold_tasks = {task.task_id: task for task in gold_dag.tasks}

    # Verify all required tasks exist
    assert "dbt_gold_dimensions" in gold_tasks
    facts = gold_tasks["dbt_gold_facts"]
    aggregates = gold_tasks["dbt_gold_aggregates"]
    test = gold_tasks["dbt_gold_test"]
    validation = gold_tasks["ge_gold_validation"]
    data_docs = gold_tasks["ge_generate_data_docs"]

    facts_upstream = {task.task_id for task in facts.upstream_list}
    assert "dbt_gold_dimensions" in facts_upstream

    aggregates_upstream = {task.task_id for task in aggregates.upstream_list}
    assert "dbt_gold_facts" in aggregates_upstream

    test_upstream = {task.task_id for task in test.upstream_list}
    assert "dbt_gold_aggregates" in test_upstream

    validation_upstream = {task.task_id for task in validation.upstream_list}
    assert "dbt_gold_test" in validation_upstream

    data_docs_upstream = {task.task_id for task in data_docs.upstream_list}
    assert "ge_gold_validation" in data_docs_upstream
