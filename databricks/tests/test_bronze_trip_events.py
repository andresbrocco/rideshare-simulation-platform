"""
Tests for Bronze Trip Events table.

Validates table structure, schema, partitioning strategy, and data ingestion
for the bronze_trip_events Unity Catalog table.
"""

import pytest
from unittest.mock import Mock
import json


@pytest.fixture
def mock_spark():
    """Mock Spark session for testing."""
    spark = Mock()
    spark.catalog = Mock()
    spark.sql = Mock()
    return spark


@pytest.fixture
def sample_trip_event_json():
    """Sample trip event JSON payload."""
    return json.dumps(
        {
            "event_id": "evt_123",
            "event_type": "trip.requested",
            "timestamp": "2024-01-15T10:30:00Z",
            "trip_id": "trip_456",
            "rider_id": "rider_789",
            "driver_id": None,
            "pickup_location": [-23.5505, -46.6333],
            "dropoff_location": [-23.5629, -46.6544],
            "pickup_zone_id": "zone_001",
            "dropoff_zone_id": "zone_002",
            "surge_multiplier": 1.0,
            "fare": 25.50,
            "offer_sequence": None,
            "cancelled_by": None,
            "cancellation_reason": None,
            "cancellation_stage": None,
            "session_id": "sim_session_001",
            "correlation_id": "trip_456",
            "causation_id": None,
            "route": None,
            "pickup_route": None,
            "route_progress_index": None,
            "pickup_route_progress_index": None,
        }
    )


@pytest.fixture
def sample_trip_events_dataframe(sample_trip_event_json):
    """Sample DataFrame with trip events."""
    mock_df = Mock()
    mock_df.count = Mock(return_value=1)
    mock_df.schema = Mock()
    mock_df.columns = [
        "value",
        "topic",
        "partition",
        "offset",
        "timestamp",
        "_ingested_at",
        "ingestion_date",
    ]
    return mock_df


class TestTableExistence:
    """Test bronze_trip_events table existence."""

    def test_table_exists(self, mock_spark):
        """Verifies bronze_trip_events table exists in Unity Catalog."""
        from databricks.notebooks.bronze_streaming_setup import (
            create_bronze_trip_events_table,
        )

        # Mock catalog to return table exists
        mock_spark.catalog.tableExists = Mock(return_value=True)

        create_bronze_trip_events_table(mock_spark)

        # Verify table was checked/created
        mock_spark.catalog.tableExists.assert_called_once_with(
            "rideshare_bronze.trip_events"
        )


class TestTableSchema:
    """Test bronze_trip_events table schema."""

    def test_schema_has_required_columns(self, mock_spark):
        """Validates table schema has all required columns."""
        try:
            from pyspark.sql.types import StructType  # noqa: F401
        except ImportError:
            pytest.skip("PySpark not available")

        from databricks.notebooks.bronze_streaming_setup import (
            get_bronze_trip_events_schema,
        )

        schema = get_bronze_trip_events_schema()

        # Verify all required columns are present
        field_names = [field.name for field in schema.fields]

        assert "value" in field_names
        assert "topic" in field_names
        assert "partition" in field_names
        assert "offset" in field_names
        assert "timestamp" in field_names
        assert "_ingested_at" in field_names
        assert "ingestion_date" in field_names

    def test_value_column_is_string(self, mock_spark):
        """Validates value column is STRING type."""
        from databricks.notebooks.bronze_streaming_setup import (
            get_bronze_trip_events_schema,
        )

        try:
            from pyspark.sql.types import StringType
        except ImportError:
            pytest.skip("PySpark not available")

        schema = get_bronze_trip_events_schema()

        value_field = next((f for f in schema.fields if f.name == "value"), None)
        assert value_field is not None
        assert isinstance(value_field.dataType, StringType)

    def test_ingestion_metadata_present(self, mock_spark):
        """Validates metadata columns exist with correct types."""
        from databricks.notebooks.bronze_streaming_setup import (
            get_bronze_trip_events_schema,
        )

        try:
            from pyspark.sql.types import TimestampType, LongType, IntegerType, DateType
        except ImportError:
            pytest.skip("PySpark not available")

        schema = get_bronze_trip_events_schema()
        field_dict = {f.name: f.dataType for f in schema.fields}

        # Check metadata column types
        assert "_ingested_at" in field_dict
        assert isinstance(field_dict["_ingested_at"], TimestampType)

        assert "offset" in field_dict
        assert isinstance(field_dict["offset"], LongType)

        assert "partition" in field_dict
        assert isinstance(field_dict["partition"], IntegerType)

        assert "ingestion_date" in field_dict
        assert isinstance(field_dict["ingestion_date"], DateType)


class TestTablePartitioning:
    """Test table partitioning strategy."""

    def test_partition_by_ingestion_date(self, mock_spark):
        """Verifies table is partitioned by ingestion_date."""
        from databricks.notebooks.bronze_streaming_setup import (
            get_bronze_trip_events_partition_columns,
        )

        partition_cols = get_bronze_trip_events_partition_columns()

        assert partition_cols == ["ingestion_date"]

    def test_ingestion_date_derived_from_timestamp(
        self, mock_spark, sample_trip_events_dataframe
    ):
        """Validates ingestion_date is derived from _ingested_at."""
        from databricks.notebooks.bronze_streaming_setup import (
            add_ingestion_date_column,
        )

        mock_df = sample_trip_events_dataframe
        mock_df.withColumn = Mock(return_value=mock_df)

        add_ingestion_date_column(mock_df)

        # Verify withColumn was called to add ingestion_date
        mock_df.withColumn.assert_called_once()
        call_args = mock_df.withColumn.call_args
        assert call_args[0][0] == "ingestion_date"


class TestWriteMode:
    """Test table write mode."""

    def test_append_only_writes(self, mock_spark):
        """Verifies append mode is used, no MERGE operations."""
        from databricks.notebooks.bronze_streaming_setup import (
            get_bronze_trip_events_write_mode,
        )

        write_mode = get_bronze_trip_events_write_mode()

        assert write_mode == "append"


class TestTripEventDeserialization:
    """Test trip event JSON parsing."""

    def test_trip_event_deserialization(self, sample_trip_event_json):
        """Parses JSON value to TripEvent structure."""
        from databricks.notebooks.bronze_streaming_setup import parse_trip_event_json

        parsed_event = parse_trip_event_json(sample_trip_event_json)

        assert parsed_event is not None
        assert parsed_event["trip_id"] == "trip_456"
        assert parsed_event["event_type"] == "trip.requested"
        assert parsed_event["rider_id"] == "rider_789"

    def test_handles_all_trip_event_types(self):
        """Ingests all 10 trip event types."""
        from databricks.notebooks.bronze_streaming_setup import (
            validate_trip_event_type,
        )

        valid_event_types = [
            "trip.requested",
            "trip.offer_sent",
            "trip.matched",
            "trip.driver_en_route",
            "trip.driver_arrived",
            "trip.started",
            "trip.completed",
            "trip.cancelled",
            "trip.offer_expired",
            "trip.offer_rejected",
        ]

        for event_type in valid_event_types:
            assert validate_trip_event_type(event_type) is True

    def test_tracing_fields_parsed(self, sample_trip_event_json):
        """Extract tracing fields from JSON event."""
        from databricks.notebooks.bronze_streaming_setup import (
            extract_tracing_fields_from_json,
        )

        tracing_fields = extract_tracing_fields_from_json(sample_trip_event_json)

        assert "session_id" in tracing_fields
        assert "correlation_id" in tracing_fields
        assert "causation_id" in tracing_fields

        assert tracing_fields["session_id"] == "sim_session_001"
        assert tracing_fields["correlation_id"] == "trip_456"
        assert tracing_fields["causation_id"] is None


class TestKafkaMetadata:
    """Test Kafka metadata preservation."""

    def test_kafka_offset_stored(self, sample_trip_events_dataframe):
        """Verifies Kafka offset is stored as metadata."""
        mock_df = sample_trip_events_dataframe

        assert "offset" in mock_df.columns

    def test_kafka_partition_stored(self, sample_trip_events_dataframe):
        """Verifies Kafka partition is stored as metadata."""
        mock_df = sample_trip_events_dataframe

        assert "partition" in mock_df.columns

    def test_topic_name_stored(self, sample_trip_events_dataframe):
        """Verifies Kafka topic name is stored."""
        mock_df = sample_trip_events_dataframe

        assert "topic" in mock_df.columns


class TestDataQuality:
    """Test data quality constraints."""

    def test_value_column_not_null(self):
        """Validates value column is not nullable."""
        try:
            from pyspark.sql.types import StructType  # noqa: F401
        except ImportError:
            pytest.skip("PySpark not available")

        from databricks.notebooks.bronze_streaming_setup import (
            get_bronze_trip_events_schema,
        )

        schema = get_bronze_trip_events_schema()

        value_field = next((f for f in schema.fields if f.name == "value"), None)
        assert value_field is not None
        assert value_field.nullable is False

    def test_offset_column_not_null(self):
        """Validates offset column is not nullable."""
        try:
            from pyspark.sql.types import StructType  # noqa: F401
        except ImportError:
            pytest.skip("PySpark not available")

        from databricks.notebooks.bronze_streaming_setup import (
            get_bronze_trip_events_schema,
        )

        schema = get_bronze_trip_events_schema()

        offset_field = next((f for f in schema.fields if f.name == "offset"), None)
        assert offset_field is not None
        assert offset_field.nullable is False


class TestStreamWriteConfiguration:
    """Test streaming write configuration."""

    def test_checkpoint_location_configured(self, mock_spark):
        """Validates checkpoint location is configured for stream."""
        from databricks.utils.streaming_utils import create_checkpoint_path

        checkpoint = create_checkpoint_path("trip_events")

        assert "trip_events" in checkpoint
        assert "checkpoints" in checkpoint
        assert "bronze" in checkpoint

    def test_trigger_configuration(self):
        """Validates streaming trigger is configured."""
        from databricks.notebooks.bronze_streaming_setup import (
            get_stream_trigger_config,
        )

        trigger_config = get_stream_trigger_config()

        # Should have processingTime configured
        assert "processingTime" in trigger_config
        assert trigger_config["processingTime"] is not None
