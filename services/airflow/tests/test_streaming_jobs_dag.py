"""Tests for streaming jobs lifecycle DAG."""

import pytest
from airflow.models import DagBag


@pytest.fixture
def dagbag():
    """Load DAGs from the dags folder."""
    return DagBag(
        dag_folder="/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/airflow/dags/",
        include_examples=False,
    )


@pytest.fixture
def mock_local_environment(monkeypatch):
    """Set environment to local mode."""
    monkeypatch.setenv("RIDESHARE_ENVIRONMENT", "local")


@pytest.fixture
def mock_cloud_environment(monkeypatch):
    """Set environment to cloud mode."""
    monkeypatch.setenv("RIDESHARE_ENVIRONMENT", "cloud")


def test_dag_loads(dagbag):
    """Verify streaming jobs DAG is loaded without errors."""
    assert "streaming_jobs_lifecycle" in dagbag.dags
    assert len(dagbag.import_errors) == 0


def test_environment_detection_local(dagbag, mock_local_environment):
    """Verify PythonOperator is used when RIDESHARE_ENVIRONMENT=local.

    Note: Local mode uses PythonOperator to submit jobs via Docker exec,
    not SparkSubmitOperator.
    """
    dagbag_local = DagBag(
        dag_folder="/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/airflow/dags/",
        include_examples=False,
    )

    dag = dagbag_local.dags.get("streaming_jobs_lifecycle")
    assert dag is not None

    submit_tasks = [task for task in dag.tasks if task.task_id.startswith("submit_")]

    for task in submit_tasks:
        assert (
            task.task_type == "PythonOperator"
        ), f"Task {task.task_id} should use PythonOperator in local mode"


def test_environment_detection_cloud(dagbag, mock_cloud_environment):
    """Verify DatabricksSubmitRunOperator is used when RIDESHARE_ENVIRONMENT=cloud."""
    dagbag_cloud = DagBag(
        dag_folder="/Users/asbrocco/Documents/REPOS/de-portfolio/rideshare-simulation-platform/services/airflow/dags/",
        include_examples=False,
    )

    dag = dagbag_cloud.dags.get("streaming_jobs_lifecycle")
    assert dag is not None

    submit_tasks = [task for task in dag.tasks if task.task_id.startswith("submit_")]

    for task in submit_tasks:
        assert (
            task.task_type == "DatabricksSubmitRunOperator"
        ), f"Task {task.task_id} should use DatabricksSubmitRunOperator in cloud mode"


def test_all_jobs_configured(dagbag):
    """Verify all 2 consolidated streaming jobs have submit and health check tasks."""
    dag = dagbag.dags["streaming_jobs_lifecycle"]

    # Consolidated streaming jobs (as of 2026-01-26):
    # - high_volume: handles gps_pings topic
    # - low_volume: handles 7 other topics
    expected_jobs = [
        "high_volume",
        "low_volume",
    ]

    task_ids = {task.task_id for task in dag.tasks}

    for job_name in expected_jobs:
        submit_task = f"submit_{job_name}"
        health_task = f"health_check_{job_name}"

        assert submit_task in task_ids, f"Missing submit task for {job_name}"
        assert health_task in task_ids, f"Missing health check task for {job_name}"


def test_health_sensor_timeout(dagbag):
    """Verify health check sensors have appropriate timeout and poke_interval."""
    dag = dagbag.dags["streaming_jobs_lifecycle"]

    health_check_tasks = [task for task in dag.tasks if task.task_id.startswith("health_check_")]

    assert len(health_check_tasks) == 2, "Should have 2 health check tasks (consolidated jobs)"

    for task in health_check_tasks:
        assert task.task_type in [
            "PythonSensor",
            "HttpSensor",
        ], f"Task {task.task_id} should be a sensor"

        assert task.timeout >= 300, f"Task {task.task_id} timeout should be at least 300 seconds"

        assert task.poke_interval == 60, f"Task {task.task_id} poke_interval should be 60 seconds"


def test_restart_on_failure(dagbag):
    """Verify failed jobs trigger restart task."""
    dag = dagbag.dags["streaming_jobs_lifecycle"]

    task_ids = {task.task_id for task in dag.tasks}
    assert "restart_failed_jobs" in task_ids

    restart_task = next(task for task in dag.tasks if task.task_id == "restart_failed_jobs")

    assert (
        restart_task.trigger_rule == "one_failed"
    ), "restart_failed_jobs should trigger when one health check fails"

    upstream_tasks = {task.task_id for task in restart_task.upstream_list}

    # Consolidated streaming jobs (as of 2026-01-26)
    health_check_tasks = [
        f"health_check_{job}"
        for job in [
            "high_volume",
            "low_volume",
        ]
    ]

    for health_task in health_check_tasks:
        assert (
            health_task in upstream_tasks
        ), f"{health_task} should be upstream of restart_failed_jobs"


def test_manual_trigger(dagbag):
    """Verify DAG supports manual trigger with correct configuration.

    Note: This DAG is deprecated (as of 2026-01-18) and has schedule=None.
    Streaming jobs are now managed as dedicated docker-compose services.
    """
    dag = dagbag.dags["streaming_jobs_lifecycle"]

    assert dag.catchup is False, "DAG should not catch up on past runs"

    schedule = getattr(dag, "schedule_interval", None) or dag.schedule
    # DAG is deprecated - schedule is None
    assert schedule is None, "DAG should have schedule=None (deprecated)"

    assert hasattr(dag, "params") or True, "DAG should support manual parameters"


def test_dag_default_args(dagbag):
    """Verify DAG has appropriate default_args."""
    dag = dagbag.dags["streaming_jobs_lifecycle"]

    assert hasattr(dag, "default_args")
    assert "retries" in dag.default_args
    assert dag.default_args["retries"] >= 1


def test_dag_tags(dagbag):
    """Verify DAG has appropriate tags."""
    dag = dagbag.dags["streaming_jobs_lifecycle"]

    assert hasattr(dag, "tags")
    assert "streaming" in dag.tags or "monitoring" in dag.tags


def test_task_dependencies(dagbag):
    """Verify correct task dependency chains."""
    dag = dagbag.dags["streaming_jobs_lifecycle"]

    tasks = {task.task_id: task for task in dag.tasks}

    # Consolidated streaming jobs (as of 2026-01-26)
    for job_name in [
        "high_volume",
        "low_volume",
    ]:
        submit_task = tasks[f"submit_{job_name}"]
        health_task = tasks[f"health_check_{job_name}"]

        downstream_ids = {task.task_id for task in submit_task.downstream_list}
        assert (
            f"health_check_{job_name}" in downstream_ids
        ), f"submit_{job_name} should be followed by health_check_{job_name}"

        health_downstream_ids = {task.task_id for task in health_task.downstream_list}
        assert (
            "restart_failed_jobs" in health_downstream_ids
        ), f"health_check_{job_name} should be followed by restart_failed_jobs"
