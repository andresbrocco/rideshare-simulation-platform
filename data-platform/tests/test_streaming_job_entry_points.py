"""Tests for streaming job entry points.

Validates that all streaming job files have proper __main__ blocks
that allow them to be executed directly via spark-submit.
"""

import ast
from pathlib import Path


class TestStreamingJobEntryPoints:
    """Verify all streaming job files have execution entry points."""

    @staticmethod
    def _get_job_files():
        """Get all streaming job Python files."""
        jobs_dir = Path(__file__).parent.parent / "streaming" / "jobs"
        return [f for f in jobs_dir.glob("*.py") if f.name != "__init__.py"]

    @staticmethod
    def _has_main_block(file_path):
        """Check if file has if __name__ == '__main__': block."""
        with open(file_path, "r") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Compare):
                    if (
                        isinstance(node.test.left, ast.Name)
                        and node.test.left.id == "__name__"
                    ):
                        for comparator in node.test.comparators:
                            if (
                                isinstance(comparator, ast.Constant)
                                and comparator.value == "__main__"
                            ):
                                return True
        return False

    @staticmethod
    def _extract_main_block_content(file_path):
        """Extract the content of the __main__ block for analysis."""
        with open(file_path, "r") as f:
            source = f.read()
            tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Compare):
                    if (
                        isinstance(node.test.left, ast.Name)
                        and node.test.left.id == "__name__"
                    ):
                        for comparator in node.test.comparators:
                            if (
                                isinstance(comparator, ast.Constant)
                                and comparator.value == "__main__"
                            ):
                                return node.body
        return []

    @staticmethod
    def _imports_module(statements, module_name):
        """Check if statements contain import for module_name."""
        for stmt in statements:
            if isinstance(stmt, ast.ImportFrom):
                if module_name in (stmt.module or ""):
                    return True
            elif isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    if module_name in alias.name:
                        return True
        return False

    @staticmethod
    def _has_spark_session_init(statements):
        """Check if SparkSession is initialized in statements."""
        for stmt in statements:
            if isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, ast.Call):
                    call_str = ast.unparse(stmt.value)
                    if "SparkSession" in call_str and "getOrCreate" in call_str:
                        return True
        return False

    @staticmethod
    def _has_kafka_config_init(statements):
        """Check if KafkaConfig is instantiated."""
        for stmt in statements:
            if isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, ast.Call):
                    if isinstance(stmt.value.func, ast.Name):
                        if stmt.value.func.id == "KafkaConfig":
                            return True
        return False

    @staticmethod
    def _has_checkpoint_config_init(statements):
        """Check if CheckpointConfig is instantiated."""
        for stmt in statements:
            if isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, ast.Call):
                    if isinstance(stmt.value.func, ast.Name):
                        if stmt.value.func.id == "CheckpointConfig":
                            return True
        return False

    @staticmethod
    def _has_error_handler_init(statements):
        """Check if ErrorHandler is instantiated."""
        for stmt in statements:
            if isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, ast.Call):
                    if isinstance(stmt.value.func, ast.Name):
                        if stmt.value.func.id == "ErrorHandler":
                            return True
        return False

    @staticmethod
    def _has_job_start_call(statements):
        """Check if job.start() is called."""
        for stmt in statements:
            if isinstance(stmt, ast.Assign):
                if isinstance(stmt.value, ast.Call):
                    if isinstance(stmt.value.func, ast.Attribute):
                        if stmt.value.func.attr == "start":
                            return True
        return False

    @staticmethod
    def _has_await_termination_call(statements):
        """Check if query.awaitTermination() is called."""
        for stmt in statements:
            if isinstance(stmt, ast.Expr):
                if isinstance(stmt.value, ast.Call):
                    if isinstance(stmt.value.func, ast.Attribute):
                        if stmt.value.func.attr == "awaitTermination":
                            return True
        return False

    def test_all_job_files_have_main_block(self):
        """All 8 streaming job files should have __main__ block."""
        job_files = self._get_job_files()
        assert len(job_files) == 8, f"Expected 8 job files, found {len(job_files)}"

        missing_main = []
        for job_file in job_files:
            if not self._has_main_block(job_file):
                missing_main.append(job_file.name)

        assert not missing_main, f"Jobs missing __main__ block: {missing_main}"

    def test_trips_job_has_spark_session(self):
        """trips_streaming_job.py should initialize SparkSession."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "trips_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)
        assert self._has_spark_session_init(main_block), "SparkSession not initialized"

    def test_trips_job_has_kafka_config(self):
        """trips_streaming_job.py should initialize KafkaConfig."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "trips_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)
        assert self._has_kafka_config_init(main_block), "KafkaConfig not initialized"

    def test_trips_job_has_checkpoint_config(self):
        """trips_streaming_job.py should initialize CheckpointConfig."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "trips_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)
        assert self._has_checkpoint_config_init(
            main_block
        ), "CheckpointConfig not initialized"

    def test_trips_job_has_error_handler(self):
        """trips_streaming_job.py should initialize ErrorHandler."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "trips_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)
        assert self._has_error_handler_init(main_block), "ErrorHandler not initialized"

    def test_trips_job_starts_streaming(self):
        """trips_streaming_job.py should call job.start()."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "trips_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)
        assert self._has_job_start_call(main_block), "job.start() not called"

    def test_trips_job_awaits_termination(self):
        """trips_streaming_job.py should call query.awaitTermination()."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "trips_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)
        assert self._has_await_termination_call(
            main_block
        ), "query.awaitTermination() not called"

    def test_gps_pings_job_has_main_components(self):
        """gps_pings_streaming_job.py should have all required components."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "gps_pings_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)

        assert self._has_spark_session_init(main_block), "SparkSession not initialized"
        assert self._has_kafka_config_init(main_block), "KafkaConfig not initialized"
        assert self._has_checkpoint_config_init(
            main_block
        ), "CheckpointConfig not initialized"
        assert self._has_job_start_call(main_block), "job.start() not called"
        assert self._has_await_termination_call(
            main_block
        ), "query.awaitTermination() not called"

    def test_driver_status_job_has_main_components(self):
        """driver_status_streaming_job.py should have all required components."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "driver_status_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)

        assert self._has_spark_session_init(main_block), "SparkSession not initialized"
        assert self._has_kafka_config_init(main_block), "KafkaConfig not initialized"
        assert self._has_checkpoint_config_init(
            main_block
        ), "CheckpointConfig not initialized"
        assert self._has_job_start_call(main_block), "job.start() not called"
        assert self._has_await_termination_call(
            main_block
        ), "query.awaitTermination() not called"

    def test_driver_profiles_job_has_main_components(self):
        """driver_profiles_streaming_job.py should have all required components."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "driver_profiles_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)

        assert self._has_spark_session_init(main_block), "SparkSession not initialized"
        assert self._has_kafka_config_init(main_block), "KafkaConfig not initialized"
        assert self._has_checkpoint_config_init(
            main_block
        ), "CheckpointConfig not initialized"
        assert self._has_job_start_call(main_block), "job.start() not called"
        assert self._has_await_termination_call(
            main_block
        ), "query.awaitTermination() not called"

    def test_rider_profiles_job_has_main_components(self):
        """rider_profiles_streaming_job.py should have all required components."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "rider_profiles_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)

        assert self._has_spark_session_init(main_block), "SparkSession not initialized"
        assert self._has_kafka_config_init(main_block), "KafkaConfig not initialized"
        assert self._has_checkpoint_config_init(
            main_block
        ), "CheckpointConfig not initialized"
        assert self._has_job_start_call(main_block), "job.start() not called"
        assert self._has_await_termination_call(
            main_block
        ), "query.awaitTermination() not called"

    def test_payments_job_has_main_components(self):
        """payments_streaming_job.py should have all required components."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "payments_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)

        assert self._has_spark_session_init(main_block), "SparkSession not initialized"
        assert self._has_kafka_config_init(main_block), "KafkaConfig not initialized"
        assert self._has_checkpoint_config_init(
            main_block
        ), "CheckpointConfig not initialized"
        assert self._has_job_start_call(main_block), "job.start() not called"
        assert self._has_await_termination_call(
            main_block
        ), "query.awaitTermination() not called"

    def test_ratings_job_has_main_components(self):
        """ratings_streaming_job.py should have all required components."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "ratings_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)

        assert self._has_spark_session_init(main_block), "SparkSession not initialized"
        assert self._has_kafka_config_init(main_block), "KafkaConfig not initialized"
        assert self._has_checkpoint_config_init(
            main_block
        ), "CheckpointConfig not initialized"
        assert self._has_job_start_call(main_block), "job.start() not called"
        assert self._has_await_termination_call(
            main_block
        ), "query.awaitTermination() not called"

    def test_surge_updates_job_has_main_components(self):
        """surge_updates_streaming_job.py should have all required components."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "surge_updates_streaming_job.py"
        )
        main_block = self._extract_main_block_content(job_file)

        assert self._has_spark_session_init(main_block), "SparkSession not initialized"
        assert self._has_kafka_config_init(main_block), "KafkaConfig not initialized"
        assert self._has_checkpoint_config_init(
            main_block
        ), "CheckpointConfig not initialized"
        assert self._has_job_start_call(main_block), "job.start() not called"
        assert self._has_await_termination_call(
            main_block
        ), "query.awaitTermination() not called"

    def test_trips_job_uses_environment_variables(self):
        """trips_streaming_job.py should read bootstrap_servers from environment."""
        job_file = (
            Path(__file__).parent.parent
            / "streaming"
            / "jobs"
            / "trips_streaming_job.py"
        )
        with open(job_file, "r") as f:
            content = f.read()

        assert (
            "KAFKA_BOOTSTRAP_SERVERS" in content
        ), "Should read KAFKA_BOOTSTRAP_SERVERS env var"
        assert "CHECKPOINT_PATH" in content, "Should read CHECKPOINT_PATH env var"

    def test_all_jobs_have_proper_app_names(self):
        """Each job should have a descriptive SparkSession appName."""
        job_files = self._get_job_files()

        for job_file in job_files:
            with open(job_file, "r") as f:
                content = f.read()

            if self._has_main_block(job_file):
                assert (
                    "appName" in content
                ), f"{job_file.name} missing appName in SparkSession"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
