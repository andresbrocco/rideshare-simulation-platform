"""
Tests for Bronze Remaining Tables (Ratings, Payments, Surge Updates, Driver Status).

Validates table structure, schema, partitioning, and streaming configuration
for bronze_ratings, bronze_payments, bronze_surge_updates, and bronze_driver_status
Unity Catalog tables.
"""

import json
from unittest.mock import Mock

import pytest


@pytest.fixture
def mock_spark():
    """Mock Spark session for testing."""
    spark = Mock()
    spark.catalog = Mock()
    spark.sql = Mock()
    return spark


@pytest.fixture
def sample_rating_json():
    """Sample rating event JSON payload."""
    return json.dumps(
        {
            "event_id": "evt_rating_123",
            "event_type": "rating.submitted",
            "timestamp": "2024-01-15T10:30:00Z",
            "trip_id": "trip_456",
            "rater_id": "rider_789",
            "ratee_id": "driver_001",
            "rating": 5,
            "comment": "Great ride!",
            "session_id": "sim_session_001",
            "correlation_id": "trip_456",
            "causation_id": "trip_completed_evt_123",
        }
    )


@pytest.fixture
def sample_payment_json():
    """Sample payment event JSON payload."""
    return json.dumps(
        {
            "event_id": "evt_payment_123",
            "event_type": "payment.processed",
            "timestamp": "2024-01-15T10:30:00Z",
            "trip_id": "trip_456",
            "rider_id": "rider_789",
            "amount": 25.50,
            "payment_method": "credit_card",
            "status": "success",
            "session_id": "sim_session_001",
            "correlation_id": "trip_456",
            "causation_id": "trip_completed_evt_123",
        }
    )


@pytest.fixture
def sample_surge_update_json():
    """Sample surge update event JSON payload."""
    return json.dumps(
        {
            "event_id": "evt_surge_123",
            "event_type": "surge.updated",
            "timestamp": "2024-01-15T10:30:00Z",
            "zone_id": "zone_001",
            "surge_multiplier": 1.5,
            "available_drivers": 5,
            "pending_requests": 10,
            "session_id": "sim_session_001",
            "correlation_id": "surge_calc_001",
            "causation_id": None,
        }
    )


@pytest.fixture
def sample_driver_status_json():
    """Sample driver status event JSON payload."""
    return json.dumps(
        {
            "event_id": "evt_status_123",
            "event_type": "driver.status_changed",
            "timestamp": "2024-01-15T10:30:00Z",
            "driver_id": "driver_001",
            "status": "available",
            "previous_status": "on_trip",
            "session_id": "sim_session_001",
            "correlation_id": "driver_001",
            "causation_id": "trip_completed_evt_123",
        }
    )


# ===== RATINGS TABLE TESTS =====


class TestRatingsTableExistence:
    """Test bronze_ratings table existence."""

    def test_bronze_ratings_table_exists(self, mock_spark):
        """Verifies bronze_ratings table exists in Unity Catalog."""
        from databricks.notebooks.bronze_ratings_stream import (
            create_bronze_ratings_table,
        )

        mock_spark.catalog.tableExists = Mock(return_value=True)

        create_bronze_ratings_table(mock_spark)

        mock_spark.catalog.tableExists.assert_called_once()


class TestRatingsTableSchema:
    """Test bronze_ratings table schema."""

    def test_ratings_schema_has_required_columns(self):
        """Validates ratings table schema has all required columns."""
        try:
            from pyspark.sql.types import StructType  # noqa: F401
        except ImportError:
            pytest.skip("PySpark not available")

        from databricks.notebooks.bronze_ratings_stream import get_ratings_schema

        schema = get_ratings_schema()
        field_names = [field.name for field in schema.fields]

        assert "value" in field_names
        assert "_ingested_at" in field_names
        assert "_kafka_partition" in field_names
        assert "_kafka_offset" in field_names
        assert "ingestion_date" in field_names


class TestRatingsPartitioning:
    """Test ratings table partitioning."""

    def test_ratings_partitioned_by_date(self):
        """Verifies ratings table is partitioned by ingestion_date."""
        from databricks.notebooks.bronze_ratings_stream import get_partition_columns

        partition_cols = get_partition_columns()

        assert partition_cols == ["ingestion_date"]


class TestRatingsCheckpoint:
    """Test ratings checkpoint configuration."""

    def test_ratings_unique_checkpoint(self):
        """Checkpoint path is unique for ratings topic."""
        from databricks.utils.streaming_utils import create_checkpoint_path

        checkpoint = create_checkpoint_path("ratings")

        assert checkpoint.endswith("ratings/")


# ===== PAYMENTS TABLE TESTS =====


class TestPaymentsTableExistence:
    """Test bronze_payments table existence."""

    def test_bronze_payments_table_exists(self, mock_spark):
        """Verifies bronze_payments table exists in Unity Catalog."""
        from databricks.notebooks.bronze_payments_stream import (
            create_bronze_payments_table,
        )

        mock_spark.catalog.tableExists = Mock(return_value=True)

        create_bronze_payments_table(mock_spark)

        mock_spark.catalog.tableExists.assert_called_once()


class TestPaymentsTableSchema:
    """Test bronze_payments table schema."""

    def test_payments_schema_has_required_columns(self):
        """Validates payments table schema has all required columns."""
        try:
            from pyspark.sql.types import StructType  # noqa: F401
        except ImportError:
            pytest.skip("PySpark not available")

        from databricks.notebooks.bronze_payments_stream import get_payments_schema

        schema = get_payments_schema()
        field_names = [field.name for field in schema.fields]

        assert "value" in field_names
        assert "_ingested_at" in field_names
        assert "_kafka_partition" in field_names
        assert "_kafka_offset" in field_names
        assert "ingestion_date" in field_names


class TestPaymentsCheckpoint:
    """Test payments checkpoint configuration."""

    def test_payments_unique_checkpoint(self):
        """Checkpoint path is unique for payments topic."""
        from databricks.utils.streaming_utils import create_checkpoint_path

        checkpoint = create_checkpoint_path("payments")

        assert checkpoint.endswith("payments/")


# ===== SURGE UPDATES TABLE TESTS =====


class TestSurgeUpdatesTableExistence:
    """Test bronze_surge_updates table existence."""

    def test_bronze_surge_updates_table_exists(self, mock_spark):
        """Verifies bronze_surge_updates table exists in Unity Catalog."""
        from databricks.notebooks.bronze_surge_updates_stream import (
            create_bronze_surge_updates_table,
        )

        mock_spark.catalog.tableExists = Mock(return_value=True)

        create_bronze_surge_updates_table(mock_spark)

        mock_spark.catalog.tableExists.assert_called_once()


class TestSurgeUpdatesPartitioning:
    """Test surge updates table partitioning."""

    def test_surge_updates_partitioned_by_date(self):
        """Verifies surge updates table is partitioned by ingestion_date."""
        from databricks.notebooks.bronze_surge_updates_stream import (
            get_partition_columns,
        )

        partition_cols = get_partition_columns()

        assert partition_cols == ["ingestion_date"]


class TestSurgeUpdatesCheckpoint:
    """Test surge updates checkpoint configuration."""

    def test_surge_updates_unique_checkpoint(self):
        """Checkpoint path is unique for surge-updates topic."""
        from databricks.utils.streaming_utils import create_checkpoint_path

        checkpoint = create_checkpoint_path("surge-updates")

        assert checkpoint.endswith("surge-updates/")


# ===== DRIVER STATUS TABLE TESTS =====


class TestDriverStatusTableExistence:
    """Test bronze_driver_status table existence."""

    def test_bronze_driver_status_table_exists(self, mock_spark):
        """Verifies bronze_driver_status table exists in Unity Catalog."""
        from databricks.notebooks.bronze_driver_status_stream import (
            create_bronze_driver_status_table,
        )

        mock_spark.catalog.tableExists = Mock(return_value=True)

        create_bronze_driver_status_table(mock_spark)

        mock_spark.catalog.tableExists.assert_called_once()


class TestDriverStatusPartitioning:
    """Test driver status table partitioning."""

    def test_driver_status_partitioned_by_date(self):
        """Verifies driver status table is partitioned by ingestion_date."""
        from databricks.notebooks.bronze_driver_status_stream import (
            get_partition_columns,
        )

        partition_cols = get_partition_columns()

        assert partition_cols == ["ingestion_date"]


class TestDriverStatusCheckpoint:
    """Test driver status checkpoint configuration."""

    def test_driver_status_unique_checkpoint(self):
        """Checkpoint path is unique for driver-status topic."""
        from databricks.utils.streaming_utils import create_checkpoint_path

        checkpoint = create_checkpoint_path("driver-status")

        assert checkpoint.endswith("driver-status/")


# ===== CROSS-TABLE TESTS =====


class TestTracingFieldsParsed:
    """Test distributed tracing field extraction."""

    def test_tracing_fields_parsed(self, sample_rating_json):
        """Extract tracing fields from JSON event."""
        from databricks.notebooks.bronze_ratings_stream import extract_tracing_fields

        tracing = extract_tracing_fields(sample_rating_json)

        assert "session_id" in tracing
        assert "correlation_id" in tracing
        assert "causation_id" in tracing


class TestAppendOnlyMode:
    """Test all tables use append-only mode."""

    def test_all_tables_append_only(self):
        """Verifies append-only mode for all tables."""
        from databricks.notebooks.bronze_driver_status_stream import (
            get_write_mode as status_mode,
        )
        from databricks.notebooks.bronze_payments_stream import (
            get_write_mode as payments_mode,
        )
        from databricks.notebooks.bronze_ratings_stream import (
            get_write_mode as ratings_mode,
        )
        from databricks.notebooks.bronze_surge_updates_stream import (
            get_write_mode as surge_mode,
        )

        assert ratings_mode() == "append"
        assert payments_mode() == "append"
        assert surge_mode() == "append"
        assert status_mode() == "append"
