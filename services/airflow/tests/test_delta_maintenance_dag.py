"""Tests for Delta maintenance DAG."""

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
    """Verify Delta maintenance DAG is loaded without errors."""
    assert "delta_maintenance" in dagbag.dags
    assert len(dagbag.import_errors) == 0


def test_dag_schedule(dagbag):
    """Verify DAG runs at 3 AM daily."""
    dag = dagbag.dags["delta_maintenance"]
    schedule = getattr(dag, "schedule_interval", None) or dag.schedule
    assert schedule == "0 3 * * *"


def test_no_catchup(dagbag):
    """Verify DAG doesn't catch up on past runs."""
    dag = dagbag.dags["delta_maintenance"]
    assert dag.catchup is False


def test_max_active_tasks(dagbag):
    """Verify DAG limits parallel operations to 4."""
    dag = dagbag.dags["delta_maintenance"]
    assert dag.max_active_tasks == 4


class TestBronzeTables:
    """Tests for Bronze table tasks."""

    EXPECTED_BRONZE_TABLES = [
        "bronze_trips",
        "bronze_gps_pings",
        "bronze_driver_status",
        "bronze_surge_updates",
        "bronze_ratings",
        "bronze_payments",
        "bronze_driver_profiles",
        "bronze_rider_profiles",
    ]

    def test_all_bronze_tables_have_optimize_tasks(self, dagbag):
        """Verify all 8 Bronze tables have OPTIMIZE tasks."""
        dag = dagbag.dags["delta_maintenance"]
        task_ids = {task.task_id for task in dag.tasks}

        for table in self.EXPECTED_BRONZE_TABLES:
            assert f"optimize_{table}" in task_ids

    def test_all_bronze_tables_have_vacuum_tasks(self, dagbag):
        """Verify all 8 Bronze tables have VACUUM tasks."""
        dag = dagbag.dags["delta_maintenance"]
        task_ids = {task.task_id for task in dag.tasks}

        for table in self.EXPECTED_BRONZE_TABLES:
            assert f"vacuum_{table}" in task_ids


class TestDLQTables:
    """Tests for DLQ table tasks."""

    EXPECTED_DLQ_TABLES = [
        "dlq_trips",
        "dlq_gps_pings",
        "dlq_driver_status",
        "dlq_surge_updates",
        "dlq_ratings",
        "dlq_payments",
        "dlq_driver_profiles",
        "dlq_rider_profiles",
    ]

    def test_all_dlq_tables_have_optimize_tasks(self, dagbag):
        """Verify all 8 DLQ tables have OPTIMIZE tasks."""
        dag = dagbag.dags["delta_maintenance"]
        task_ids = {task.task_id for task in dag.tasks}

        for table in self.EXPECTED_DLQ_TABLES:
            assert f"optimize_{table}" in task_ids

    def test_all_dlq_tables_have_vacuum_tasks(self, dagbag):
        """Verify all 8 DLQ tables have VACUUM tasks."""
        dag = dagbag.dags["delta_maintenance"]
        task_ids = {task.task_id for task in dag.tasks}

        for table in self.EXPECTED_DLQ_TABLES:
            assert f"vacuum_{table}" in task_ids


class TestTaskCount:
    """Tests for total task counts."""

    def test_total_tables(self, dagbag):
        """Verify total of 16 tables (8 Bronze + 8 DLQ)."""
        dag = dagbag.dags["delta_maintenance"]
        # Exclude barrier tasks (optimize_complete, vacuum_complete)
        optimize_tasks = [
            t
            for t in dag.tasks
            if t.task_id.startswith("optimize_") and t.task_id != "optimize_complete"
        ]
        vacuum_tasks = [
            t
            for t in dag.tasks
            if t.task_id.startswith("vacuum_") and t.task_id != "vacuum_complete"
        ]

        assert len(optimize_tasks) == 16
        assert len(vacuum_tasks) == 16


class TestTaskDependencies:
    """Tests for task dependency structure."""

    def test_start_task_exists(self, dagbag):
        """Verify start task exists."""
        dag = dagbag.dags["delta_maintenance"]
        task_ids = {task.task_id for task in dag.tasks}
        assert "start" in task_ids

    def test_optimize_complete_barrier_exists(self, dagbag):
        """Verify optimize_complete barrier task exists."""
        dag = dagbag.dags["delta_maintenance"]
        task_ids = {task.task_id for task in dag.tasks}
        assert "optimize_complete" in task_ids

    def test_vacuum_complete_barrier_exists(self, dagbag):
        """Verify vacuum_complete barrier task exists."""
        dag = dagbag.dags["delta_maintenance"]
        task_ids = {task.task_id for task in dag.tasks}
        assert "vacuum_complete" in task_ids

    def test_summarize_task_exists(self, dagbag):
        """Verify summarize task exists."""
        dag = dagbag.dags["delta_maintenance"]
        task_ids = {task.task_id for task in dag.tasks}
        assert "summarize" in task_ids

    def test_optimize_runs_before_vacuum(self, dagbag):
        """Verify OPTIMIZE tasks complete before VACUUM tasks start."""
        dag = dagbag.dags["delta_maintenance"]
        tasks = {task.task_id: task for task in dag.tasks}

        # All vacuum tasks (except barrier) should have optimize_complete as upstream
        for task_id, task in tasks.items():
            if task_id.startswith("vacuum_") and task_id != "vacuum_complete":
                upstream_ids = {t.task_id for t in task.upstream_list}
                assert "optimize_complete" in upstream_ids

    def test_optimize_tasks_depend_on_start(self, dagbag):
        """Verify all OPTIMIZE tasks depend on start."""
        dag = dagbag.dags["delta_maintenance"]
        tasks = {task.task_id: task for task in dag.tasks}

        for task_id, task in tasks.items():
            if task_id.startswith("optimize_") and task_id != "optimize_complete":
                upstream_ids = {t.task_id for t in task.upstream_list}
                assert "start" in upstream_ids

    def test_summarize_depends_on_vacuum_complete(self, dagbag):
        """Verify summarize task depends on vacuum_complete."""
        dag = dagbag.dags["delta_maintenance"]
        tasks = {task.task_id: task for task in dag.tasks}

        summarize_task = tasks["summarize"]
        upstream_ids = {t.task_id for t in summarize_task.upstream_list}
        assert "vacuum_complete" in upstream_ids


class TestTaskConfiguration:
    """Tests for task configuration."""

    def test_dag_tags(self, dagbag):
        """Verify DAG has appropriate tags."""
        dag = dagbag.dags["delta_maintenance"]
        assert "delta" in dag.tags
        assert "maintenance" in dag.tags
        assert "bronze" in dag.tags

    def test_default_args_has_retries(self, dagbag):
        """Verify default args include retries."""
        dag = dagbag.dags["delta_maintenance"]
        assert "retries" in dag.default_args
        assert dag.default_args["retries"] >= 1
