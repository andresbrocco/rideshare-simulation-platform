"""Pytest configuration and shared fixtures for Bronze streaming tests.

This module provides reusable fixtures for testing Spark Structured Streaming
jobs that ingest data from Kafka into Bronze Delta tables.
"""

import sys
from pathlib import Path
import importlib.util

# Create 'spark_streaming' module alias pointing to parent directory
# Mimics Docker mount: services/spark-streaming -> /opt/spark_streaming
# This allows imports like 'from spark_streaming.config import ...' to work locally
spark_streaming_dir = Path(__file__).resolve().parent.parent
if "spark_streaming" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "spark_streaming",
        spark_streaming_dir / "__init__.py",
        submodule_search_locations=[str(spark_streaming_dir)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["spark_streaming"] = module
    spec.loader.exec_module(module)

import pytest  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402


@pytest.fixture(scope="session")
def spark_session():
    """Create a SparkSession configured for Delta Lake testing.

    This fixture creates a local Spark session with Delta Lake support.
    The session is shared across all tests in the session for efficiency.

    Yields:
        SparkSession: Configured Spark session with Delta Lake extensions.
    """
    try:
        from pyspark.sql import SparkSession
        from delta import configure_spark_with_delta_pip

        builder = (
            SparkSession.builder.appName("BronzeStreamingTests")
            .master("local[2]")
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config(
                "spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog",
            )
            .config("spark.sql.shuffle.partitions", "2")
            .config("spark.ui.enabled", "false")
            .config("spark.driver.memory", "1g")
        )

        spark = configure_spark_with_delta_pip(builder).getOrCreate()
        yield spark
        spark.stop()
    except ImportError:
        # Fall back to mock if PySpark not available
        yield MagicMock()


@pytest.fixture
def mock_spark():
    """Create a mock SparkSession for unit testing without Spark dependency.

    Returns:
        MagicMock: Mock SparkSession object.
    """
    return MagicMock()


@pytest.fixture
def temp_checkpoint_dir(tmp_path):
    """Create a temporary checkpoint directory for streaming jobs.

    Args:
        tmp_path: pytest built-in fixture for temporary directories.

    Returns:
        str: Path to the temporary checkpoint directory.
    """
    checkpoint_dir = tmp_path / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return str(checkpoint_dir)


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory for Delta tables.

    Args:
        tmp_path: pytest built-in fixture for temporary directories.

    Returns:
        str: Path to the temporary output directory.
    """
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return str(output_dir)


@pytest.fixture
def temp_dlq_dir(tmp_path):
    """Create a temporary directory for DLQ tables.

    Args:
        tmp_path: pytest built-in fixture for temporary directories.

    Returns:
        str: Path to the temporary DLQ directory.
    """
    dlq_dir = tmp_path / "dlq"
    dlq_dir.mkdir(parents=True, exist_ok=True)
    return str(dlq_dir)


@pytest.fixture
def kafka_config():
    """Create test Kafka configuration.

    Returns:
        KafkaConfig: Configuration for test Kafka connection.
    """
    from spark_streaming.config.kafka_config import KafkaConfig

    return KafkaConfig(
        bootstrap_servers="kafka:9092",
        schema_registry_url="http://schema-registry:8085",
    )


@pytest.fixture
def checkpoint_config(temp_checkpoint_dir):
    """Create test checkpoint configuration.

    Args:
        temp_checkpoint_dir: Temporary checkpoint directory fixture.

    Returns:
        CheckpointConfig: Configuration for test checkpointing.
    """
    from spark_streaming.config.checkpoint_config import CheckpointConfig

    return CheckpointConfig(checkpoint_path=temp_checkpoint_dir)


@pytest.fixture
def error_handler(temp_dlq_dir):
    """Create test error handler.

    Args:
        temp_dlq_dir: Temporary DLQ directory fixture.

    Returns:
        ErrorHandler: Error handler for test DLQ routing.
    """
    from spark_streaming.utils.error_handler import ErrorHandler

    return ErrorHandler(dlq_table_path=temp_dlq_dir)
