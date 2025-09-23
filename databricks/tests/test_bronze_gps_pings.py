"""
Tests for Bronze GPS Pings table.

Validates table structure, schema, partitioning strategy, high-volume
ingestion, and data quality for the bronze_gps_pings Unity Catalog table.
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
def sample_driver_gps_ping_json():
    """Sample driver GPS ping JSON payload."""
    return json.dumps(
        {
            "event_id": "evt_gps_001",
            "entity_type": "driver",
            "entity_id": "driver_123",
            "timestamp": "2024-01-15T10:30:45Z",
            "location": [-23.5505, -46.6333],
            "heading": 270,
            "speed": 45.5,
            "accuracy": 10.0,
            "trip_id": "trip_456",
            "session_id": "sim_session_001",
            "correlation_id": "trip_456",
            "causation_id": "evt_trip_start_001",
            "trip_state": "STARTED",
            "route_progress_index": 12,
            "pickup_route_progress_index": None,
        }
    )


@pytest.fixture
def sample_rider_gps_ping_json():
    """Sample rider GPS ping JSON payload."""
    return json.dumps(
        {
            "event_id": "evt_gps_002",
            "entity_type": "rider",
            "entity_id": "rider_789",
            "timestamp": "2024-01-15T10:30:47Z",
            "location": [-23.5629, -46.6544],
            "heading": None,
            "speed": None,
            "accuracy": 15.0,
            "trip_id": "trip_456",
            "session_id": "sim_session_001",
            "correlation_id": "trip_456",
            "causation_id": "evt_trip_start_001",
            "trip_state": "STARTED",
            "route_progress_index": 8,
            "pickup_route_progress_index": None,
        }
    )


@pytest.fixture
def sample_gps_pings_dataframe():
    """Sample DataFrame with GPS pings."""
    mock_df = Mock()
    mock_df.count = Mock(return_value=2)
    mock_df.schema = Mock()
    mock_df.columns = [
        "value",
        "topic",
        "partition",
        "offset",
        "timestamp",
        "_ingested_at",
        "_kafka_partition",
        "_kafka_offset",
        "_kafka_timestamp",
        "ingestion_date",
        "entity_type",
        "session_id",
        "correlation_id",
        "causation_id",
    ]
    return mock_df


class TestTableExistence:
    """Test bronze_gps_pings table existence."""

    def test_table_exists(self, mock_spark):
        """Verifies bronze_gps_pings table exists in Unity Catalog."""
        from databricks.notebooks.bronze_gps_pings_stream import (
            create_bronze_gps_pings_table,
        )

        # Mock catalog to return table exists
        mock_spark.catalog.tableExists = Mock(return_value=True)

        create_bronze_gps_pings_table(mock_spark)

        # Verify table was checked/created
        mock_spark.catalog.tableExists.assert_called_once_with(
            "rideshare_bronze.gps_pings"
        )


class TestTableSchema:
    """Test bronze_gps_pings table schema."""

    def test_schema_has_required_columns(self, mock_spark):
        """Validates table schema has all required columns."""
        try:
            from pyspark.sql.types import StructType  # noqa: F401
        except ImportError:
            pytest.skip("PySpark not available")

        from databricks.notebooks.bronze_gps_pings_stream import (
            get_bronze_gps_pings_schema,
        )

        schema = get_bronze_gps_pings_schema()

        # Verify all required columns are present
        field_names = [field.name for field in schema.fields]

        assert "value" in field_names
        assert "_ingested_at" in field_names
        assert "ingestion_date" in field_names
        assert "entity_type" in field_names
        assert "_kafka_partition" in field_names
        assert "_kafka_offset" in field_names
        assert "_kafka_timestamp" in field_names


class TestTablePartitioning:
    """Test table partitioning strategy."""

    def test_partition_by_ingestion_date_and_entity_type(self, mock_spark):
        """Verifies dual partitioning by ingestion_date and entity_type."""
        from databricks.notebooks.bronze_gps_pings_stream import (
            get_bronze_gps_pings_partition_columns,
        )

        partition_cols = get_bronze_gps_pings_partition_columns()

        assert partition_cols == ["ingestion_date", "entity_type"]


class TestEntityTypeExtraction:
    """Test entity_type field extraction from JSON."""

    def test_entity_type_extraction(self, sample_driver_gps_ping_json):
        """Extracts entity_type from JSON."""
        from databricks.notebooks.bronze_gps_pings_stream import (
            extract_entity_type_from_json,
        )

        entity_type = extract_entity_type_from_json(sample_driver_gps_ping_json)

        assert entity_type == "driver"

    def test_driver_and_rider_separation(
        self, sample_driver_gps_ping_json, sample_rider_gps_ping_json
    ):
        """Separates driver and rider entity types."""
        from databricks.notebooks.bronze_gps_pings_stream import (
            extract_entity_type_from_json,
        )

        driver_type = extract_entity_type_from_json(sample_driver_gps_ping_json)
        rider_type = extract_entity_type_from_json(sample_rider_gps_ping_json)

        assert driver_type == "driver"
        assert rider_type == "rider"


class TestHighVolumeConfiguration:
    """Test high-volume ingestion configuration."""

    def test_high_volume_ingestion(self):
        """Handles high throughput with maxOffsetsPerTrigger config."""
        from databricks.notebooks.bronze_gps_pings_stream import (
            get_max_offsets_per_trigger,
        )

        max_offsets = get_max_offsets_per_trigger()

        # Should be 50000 to handle up to 800 pings/sec * 60 sec = 48k/min
        assert max_offsets == 50000

    def test_backpressure_config(self):
        """Validates maxOffsetsPerTrigger setting for backpressure control."""
        from databricks.notebooks.bronze_gps_pings_stream import (
            get_stream_config,
        )

        stream_config = get_stream_config()

        assert "maxOffsetsPerTrigger" in stream_config
        assert stream_config["maxOffsetsPerTrigger"] == 50000


class TestZOrderOptimization:
    """Test Z-ORDER optimization configuration."""

    def test_zorder_on_entity_id(self):
        """Verifies Z-ORDER optimization is configured on entity_id."""
        from databricks.notebooks.bronze_gps_pings_stream import (
            get_zorder_columns,
        )

        zorder_cols = get_zorder_columns()

        assert zorder_cols == ["entity_id"]


class TestTracingFields:
    """Test distributed tracing field extraction."""

    def test_tracing_fields_parsed(self, sample_driver_gps_ping_json):
        """Extract tracing fields from JSON event."""
        from databricks.notebooks.bronze_gps_pings_stream import (
            extract_tracing_fields_from_json,
        )

        tracing_fields = extract_tracing_fields_from_json(sample_driver_gps_ping_json)

        assert "session_id" in tracing_fields
        assert "correlation_id" in tracing_fields
        assert "causation_id" in tracing_fields

        assert tracing_fields["session_id"] == "sim_session_001"
        assert tracing_fields["correlation_id"] == "trip_456"
        assert tracing_fields["causation_id"] == "evt_trip_start_001"


class TestStreamConfiguration:
    """Test streaming configuration."""

    def test_checkpoint_location_configured(self):
        """Validates checkpoint location is unique for gps-pings topic."""
        from databricks.utils.streaming_utils import create_checkpoint_path

        checkpoint = create_checkpoint_path("gps-pings")

        assert "gps-pings" in checkpoint
        assert "checkpoints" in checkpoint
        assert "bronze" in checkpoint

    def test_trigger_configuration(self):
        """Validates streaming trigger is configured for low latency."""
        from databricks.notebooks.bronze_gps_pings_stream import (
            get_stream_trigger_config,
        )

        trigger_config = get_stream_trigger_config()

        # Should have processingTime of 15 seconds for low latency
        assert "processingTime" in trigger_config
        assert trigger_config["processingTime"] == "15 seconds"
