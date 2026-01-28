"""Tests for streaming job entry points.

Validates that all streaming job files have proper __main__ blocks
that allow them to be executed directly via spark-submit.

Note: As of the streaming consolidation (2026-01-26), jobs are consolidated:
- bronze_ingestion_high_volume.py: handles gps_pings topic
- bronze_ingestion_low_volume.py: handles 7 other topics
- multi_topic_streaming_job.py: base class (no __main__ block)
"""

import ast
from pathlib import Path

import pytest


# Module-level marker: no Docker profiles required (file-based tests only)
pytestmark = pytest.mark.requires_profiles()


class TestStreamingJobEntryPoints:
    """Verify all streaming job files have execution entry points."""

    @staticmethod
    def _get_jobs_dir():
        """Get the path to the streaming jobs directory."""
        # Navigate from tests/integration/data_platform/ up to repo root,
        # then to services/spark-streaming/jobs/
        return (
            Path(__file__).parent.parent.parent.parent
            / "services"
            / "spark-streaming"
            / "jobs"
        )

    @staticmethod
    def _get_job_files():
        """Get all streaming job Python files (excluding __init__.py)."""
        jobs_dir = TestStreamingJobEntryPoints._get_jobs_dir()
        return [f for f in jobs_dir.glob("*.py") if f.name != "__init__.py"]

    @staticmethod
    def _get_executable_job_files():
        """Get job files that should have __main__ blocks (excludes base classes)."""
        jobs_dir = TestStreamingJobEntryPoints._get_jobs_dir()
        # Only bronze_ingestion_high_volume and bronze_ingestion_low_volume jobs are executable entry points
        # multi_topic_streaming_job.py is a base class without __main__
        return [
            jobs_dir / "bronze_ingestion_high_volume.py",
            jobs_dir / "bronze_ingestion_low_volume.py",
        ]

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

    def test_all_job_files_exist(self):
        """All 3 streaming job files should exist (2 executable + 1 base class)."""
        job_files = self._get_job_files()
        assert len(job_files) == 3, f"Expected 3 job files, found {len(job_files)}"

        expected_files = {
            "bronze_ingestion_high_volume.py",
            "bronze_ingestion_low_volume.py",
            "multi_topic_streaming_job.py",
        }
        actual_files = {f.name for f in job_files}
        assert (
            actual_files == expected_files
        ), f"Expected {expected_files}, found {actual_files}"

    def test_executable_jobs_have_main_block(self):
        """Executable job files (bronze_ingestion_high_volume, bronze_ingestion_low_volume) should have __main__ block."""
        job_files = self._get_executable_job_files()
        assert (
            len(job_files) == 2
        ), f"Expected 2 executable job files, found {len(job_files)}"

        missing_main = []
        for job_file in job_files:
            if not self._has_main_block(job_file):
                missing_main.append(job_file.name)

        assert not missing_main, f"Jobs missing __main__ block: {missing_main}"

    def test_high_volume_job_has_spark_session(self):
        """bronze_ingestion_high_volume.py should initialize SparkSession."""
        job_file = self._get_jobs_dir() / "bronze_ingestion_high_volume.py"
        main_block = self._extract_main_block_content(job_file)
        assert self._has_spark_session_init(main_block), "SparkSession not initialized"

    def test_high_volume_job_has_kafka_config(self):
        """bronze_ingestion_high_volume.py should initialize KafkaConfig."""
        job_file = self._get_jobs_dir() / "bronze_ingestion_high_volume.py"
        main_block = self._extract_main_block_content(job_file)
        assert self._has_kafka_config_init(main_block), "KafkaConfig not initialized"

    def test_high_volume_job_has_checkpoint_config(self):
        """bronze_ingestion_high_volume.py should initialize CheckpointConfig."""
        job_file = self._get_jobs_dir() / "bronze_ingestion_high_volume.py"
        main_block = self._extract_main_block_content(job_file)
        assert self._has_checkpoint_config_init(
            main_block
        ), "CheckpointConfig not initialized"

    def test_high_volume_job_has_error_handler(self):
        """bronze_ingestion_high_volume.py should initialize ErrorHandler."""
        job_file = self._get_jobs_dir() / "bronze_ingestion_high_volume.py"
        main_block = self._extract_main_block_content(job_file)
        assert self._has_error_handler_init(main_block), "ErrorHandler not initialized"

    def test_high_volume_job_starts_streaming(self):
        """bronze_ingestion_high_volume.py should call job.start()."""
        job_file = self._get_jobs_dir() / "bronze_ingestion_high_volume.py"
        main_block = self._extract_main_block_content(job_file)
        assert self._has_job_start_call(main_block), "job.start() not called"

    def test_high_volume_job_awaits_termination(self):
        """bronze_ingestion_high_volume.py should call query.awaitTermination()."""
        job_file = self._get_jobs_dir() / "bronze_ingestion_high_volume.py"
        main_block = self._extract_main_block_content(job_file)
        assert self._has_await_termination_call(
            main_block
        ), "query.awaitTermination() not called"

    def test_low_volume_job_has_main_components(self):
        """bronze_ingestion_low_volume.py should have all required components."""
        job_file = self._get_jobs_dir() / "bronze_ingestion_low_volume.py"
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

    def test_high_volume_job_uses_environment_variables(self):
        """bronze_ingestion_high_volume.py should read config from environment."""
        job_file = self._get_jobs_dir() / "bronze_ingestion_high_volume.py"
        with open(job_file, "r") as f:
            content = f.read()

        assert (
            "KAFKA_BOOTSTRAP_SERVERS" in content
        ), "Should read KAFKA_BOOTSTRAP_SERVERS env var"
        # Jobs read CHECKPOINT_PATH; Docker Compose sets CHECKPOINT_BASE_PATH
        # which the job uses as a base for topic-specific checkpoint directories
        assert "CHECKPOINT_PATH" in content, "Should read CHECKPOINT_PATH env var"

    def test_low_volume_job_uses_environment_variables(self):
        """bronze_ingestion_low_volume.py should read config from environment."""
        job_file = self._get_jobs_dir() / "bronze_ingestion_low_volume.py"
        with open(job_file, "r") as f:
            content = f.read()

        assert (
            "KAFKA_BOOTSTRAP_SERVERS" in content
        ), "Should read KAFKA_BOOTSTRAP_SERVERS env var"
        # Jobs read CHECKPOINT_PATH; Docker Compose sets CHECKPOINT_BASE_PATH
        # which the job uses as a base for topic-specific checkpoint directories
        assert "CHECKPOINT_PATH" in content, "Should read CHECKPOINT_PATH env var"

    def test_executable_jobs_have_proper_app_names(self):
        """Each executable job should have a descriptive SparkSession appName."""
        job_files = self._get_executable_job_files()

        for job_file in job_files:
            with open(job_file, "r") as f:
                content = f.read()

            assert (
                "appName" in content
            ), f"{job_file.name} missing appName in SparkSession"

    def test_multi_topic_base_class_has_no_main(self):
        """multi_topic_streaming_job.py is a base class and should NOT have __main__."""
        job_file = self._get_jobs_dir() / "multi_topic_streaming_job.py"
        assert not self._has_main_block(
            job_file
        ), "Base class should not have __main__ block"


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
