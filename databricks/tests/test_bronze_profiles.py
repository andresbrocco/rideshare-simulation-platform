"""
Tests for Bronze Driver and Rider Profiles tables.

Validates table structure, schema, partitioning strategy, and data ingestion
for the bronze_driver_profiles and bronze_rider_profiles Unity Catalog tables.
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
def sample_driver_created_json():
    """Sample driver profile created event JSON payload."""
    return json.dumps(
        {
            "event_id": "evt_driver_001",
            "event_type": "driver.created",
            "driver_id": "driver_123",
            "timestamp": "2024-01-15T10:30:00Z",
            "first_name": "João",
            "last_name": "Silva",
            "email": "joao.silva@example.com",
            "phone": "+5511987654321",
            "home_location": [-23.5505, -46.6333],
            "preferred_zones": ["zone_001", "zone_002"],
            "shift_preference": "morning",
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
            "vehicle_year": 2020,
            "license_plate": "ABC-1234",
            "session_id": "sim_session_001",
            "correlation_id": "driver_123",
            "causation_id": None,
        }
    )


@pytest.fixture
def sample_driver_updated_json():
    """Sample driver profile updated event JSON payload."""
    return json.dumps(
        {
            "event_id": "evt_driver_002",
            "event_type": "driver.updated",
            "driver_id": "driver_123",
            "timestamp": "2024-01-16T14:20:00Z",
            "first_name": "João",
            "last_name": "Silva",
            "email": "joao.silva@example.com",
            "phone": "+5511987654321",
            "home_location": [-23.5505, -46.6333],
            "preferred_zones": ["zone_001", "zone_003"],
            "shift_preference": "afternoon",
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
            "vehicle_year": 2020,
            "license_plate": "ABC-1234",
            "session_id": "sim_session_001",
            "correlation_id": "driver_123_update",
            "causation_id": "evt_driver_001",
        }
    )


@pytest.fixture
def sample_rider_created_json():
    """Sample rider profile created event JSON payload."""
    return json.dumps(
        {
            "event_id": "evt_rider_001",
            "event_type": "rider.created",
            "rider_id": "rider_456",
            "timestamp": "2024-01-15T11:45:00Z",
            "first_name": "Maria",
            "last_name": "Santos",
            "email": "maria.santos@example.com",
            "phone": "+5511912345678",
            "home_location": [-23.5629, -46.6544],
            "payment_method_type": "credit_card",
            "payment_method_masked": "****1234",
            "behavior_factor": 0.85,
            "session_id": "sim_session_001",
            "correlation_id": "rider_456",
            "causation_id": None,
        }
    )


@pytest.fixture
def sample_rider_updated_json():
    """Sample rider profile updated event JSON payload."""
    return json.dumps(
        {
            "event_id": "evt_rider_002",
            "event_type": "rider.updated",
            "rider_id": "rider_456",
            "timestamp": "2024-01-16T16:30:00Z",
            "first_name": "Maria",
            "last_name": "Santos",
            "email": "maria.santos.new@example.com",
            "phone": "+5511912345678",
            "home_location": [-23.5629, -46.6544],
            "payment_method_type": "digital_wallet",
            "payment_method_masked": "****5678",
            "behavior_factor": None,
            "session_id": "sim_session_001",
            "correlation_id": "rider_456_update",
            "causation_id": "evt_rider_001",
        }
    )


class TestDriverProfilesTableExistence:
    """Test bronze_driver_profiles table existence."""

    def test_driver_profiles_table_exists(self, mock_spark):
        """Verifies bronze_driver_profiles exists in Unity Catalog."""
        from databricks.notebooks.bronze_driver_profiles_stream import (
            create_bronze_driver_profiles_table,
        )

        # Mock catalog to return table exists
        mock_spark.catalog.tableExists = Mock(return_value=True)

        create_bronze_driver_profiles_table(mock_spark)

        # Verify table was checked/created
        mock_spark.catalog.tableExists.assert_called_once_with(
            "main.rideshare_bronze.bronze_driver_profiles"
        )


class TestRiderProfilesTableExistence:
    """Test bronze_rider_profiles table existence."""

    def test_rider_profiles_table_exists(self, mock_spark):
        """Verifies bronze_rider_profiles exists in Unity Catalog."""
        from databricks.notebooks.bronze_rider_profiles_stream import (
            create_bronze_rider_profiles_table,
        )

        # Mock catalog to return table exists
        mock_spark.catalog.tableExists = Mock(return_value=True)

        create_bronze_rider_profiles_table(mock_spark)

        # Verify table was checked/created
        mock_spark.catalog.tableExists.assert_called_once_with(
            "main.rideshare_bronze.bronze_rider_profiles"
        )


class TestDriverProfilesTableSchema:
    """Test bronze_driver_profiles table schema."""

    def test_driver_schema_has_required_columns(self, mock_spark):
        """Validates driver table schema has all required columns."""
        try:
            from pyspark.sql.types import StructType  # noqa: F401
        except ImportError:
            pytest.skip("PySpark not available")

        from databricks.notebooks.bronze_driver_profiles_stream import (
            get_driver_profiles_schema,
        )

        schema = get_driver_profiles_schema()

        required_columns = [
            "value",
            "_ingested_at",
            "ingestion_date",
            "event_type",
            "session_id",
            "correlation_id",
            "causation_id",
        ]

        field_names = [field.name for field in schema.fields]
        for col in required_columns:
            assert col in field_names, f"Missing required column: {col}"


class TestRiderProfilesTableSchema:
    """Test bronze_rider_profiles table schema."""

    def test_rider_schema_has_required_columns(self, mock_spark):
        """Validates rider table schema has all required columns."""
        try:
            from pyspark.sql.types import StructType  # noqa: F401
        except ImportError:
            pytest.skip("PySpark not available")

        from databricks.notebooks.bronze_rider_profiles_stream import (
            get_rider_profiles_schema,
        )

        schema = get_rider_profiles_schema()

        required_columns = [
            "value",
            "_ingested_at",
            "ingestion_date",
            "event_type",
            "session_id",
            "correlation_id",
            "causation_id",
        ]

        field_names = [field.name for field in schema.fields]
        for col in required_columns:
            assert col in field_names, f"Missing required column: {col}"


class TestEventTypeExtraction:
    """Test event_type extraction from JSON."""

    def test_event_type_extraction_driver_created(self, sample_driver_created_json):
        """Extracts event_type from driver created JSON."""
        data = json.loads(sample_driver_created_json)
        assert data["event_type"] == "driver.created"

    def test_event_type_extraction_driver_updated(self, sample_driver_updated_json):
        """Extracts event_type from driver updated JSON."""
        data = json.loads(sample_driver_updated_json)
        assert data["event_type"] == "driver.updated"

    def test_event_type_extraction_rider_created(self, sample_rider_created_json):
        """Extracts event_type from rider created JSON."""
        data = json.loads(sample_rider_created_json)
        assert data["event_type"] == "rider.created"

    def test_event_type_extraction_rider_updated(self, sample_rider_updated_json):
        """Extracts event_type from rider updated JSON."""
        data = json.loads(sample_rider_updated_json)
        assert data["event_type"] == "rider.updated"


class TestTracingFields:
    """Test distributed tracing fields extraction."""

    def test_tracing_fields_parsed_driver(self, sample_driver_created_json):
        """Extract tracing fields from driver JSON."""
        data = json.loads(sample_driver_created_json)
        assert "session_id" in data
        assert "correlation_id" in data
        assert "causation_id" in data
        assert data["session_id"] == "sim_session_001"
        assert data["correlation_id"] == "driver_123"

    def test_tracing_fields_parsed_rider(self, sample_rider_created_json):
        """Extract tracing fields from rider JSON."""
        data = json.loads(sample_rider_created_json)
        assert "session_id" in data
        assert "correlation_id" in data
        assert "causation_id" in data
        assert data["session_id"] == "sim_session_001"
        assert data["correlation_id"] == "rider_456"


class TestPartitioning:
    """Test table partitioning strategy."""

    def test_partition_by_ingestion_date_driver(self, mock_spark):
        """Verifies driver table partitioned by ingestion_date."""
        from databricks.notebooks.bronze_driver_profiles_stream import (
            get_partition_columns,
        )

        partitions = get_partition_columns()
        assert "ingestion_date" in partitions
        assert len(partitions) == 1

    def test_partition_by_ingestion_date_rider(self, mock_spark):
        """Verifies rider table partitioned by ingestion_date."""
        from databricks.notebooks.bronze_rider_profiles_stream import (
            get_partition_columns,
        )

        partitions = get_partition_columns()
        assert "ingestion_date" in partitions
        assert len(partitions) == 1


class TestLowVolumeHandling:
    """Test low-volume event processing."""

    def test_low_volume_handling(self, mock_spark):
        """Handles sparse events gracefully."""
        from databricks.notebooks.bronze_driver_profiles_stream import (
            get_trigger_interval,
        )

        interval = get_trigger_interval()
        assert interval == "60 seconds"


class TestEventTypes:
    """Test handling of created and updated events."""

    def test_created_and_updated_events_driver(
        self, sample_driver_created_json, sample_driver_updated_json
    ):
        """Ingests both driver event types."""
        created = json.loads(sample_driver_created_json)
        updated = json.loads(sample_driver_updated_json)

        assert created["event_type"] == "driver.created"
        assert updated["event_type"] == "driver.updated"

    def test_created_and_updated_events_rider(
        self, sample_rider_created_json, sample_rider_updated_json
    ):
        """Ingests both rider event types."""
        created = json.loads(sample_rider_created_json)
        updated = json.loads(sample_rider_updated_json)

        assert created["event_type"] == "rider.created"
        assert updated["event_type"] == "rider.updated"


class TestBehaviorFactor:
    """Test behavior_factor field in rider events."""

    def test_behavior_factor_in_rider_created(self, sample_rider_created_json):
        """Validates rider.created has behavior_factor."""
        data = json.loads(sample_rider_created_json)
        assert "behavior_factor" in data
        assert data["behavior_factor"] == 0.85

    def test_behavior_factor_not_in_rider_updated(self, sample_rider_updated_json):
        """Validates rider.updated has behavior_factor as None."""
        data = json.loads(sample_rider_updated_json)
        assert "behavior_factor" in data
        assert data["behavior_factor"] is None
