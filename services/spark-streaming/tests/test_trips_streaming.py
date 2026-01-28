"""Tests for trips topic handling via BronzeIngestionLowVolume.

These tests verify trips-specific configuration and schema validation
for Bronze layer Delta table ingestion.

Note: Batch processing behavior is tested in test_multi_topic_streaming_job.py.
Topic configuration tests are in test_remaining_streaming_jobs.py.
"""

from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    TimestampType,
)


class TestTripsSchemaValidation:
    """Tests for trips Bronze table schema validation.

    These tests verify the schema is correctly defined for trips data,
    including field types for fare, route, and metadata columns.
    """

    def test_fare_field_is_double_type(self):
        """Verify fare field is defined as DoubleType in schema."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_trips_schema

        fare_field = next((f for f in bronze_trips_schema.fields if f.name == "fare"), None)
        assert fare_field is not None, "fare field not found in schema"
        assert fare_field.dataType == DoubleType()

    def test_route_field_is_array_of_arrays(self):
        """Verify route field is defined as ArrayType(ArrayType(DoubleType)) in schema."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_trips_schema

        route_field = next((f for f in bronze_trips_schema.fields if f.name == "route"), None)
        assert route_field is not None, "route field not found in schema"
        assert route_field.dataType == ArrayType(ArrayType(DoubleType()))

    def test_surge_multiplier_field_is_double_type(self):
        """Verify surge_multiplier field is defined as DoubleType in schema."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_trips_schema

        surge_field = next(
            (f for f in bronze_trips_schema.fields if f.name == "surge_multiplier"),
            None,
        )
        assert surge_field is not None, "surge_multiplier field not found in schema"
        assert surge_field.dataType == DoubleType()

    def test_location_fields_are_arrays(self):
        """Verify pickup/dropoff location fields are ArrayType(DoubleType) in schema."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_trips_schema

        for field_name in ["pickup_location", "dropoff_location"]:
            field = next((f for f in bronze_trips_schema.fields if f.name == field_name), None)
            assert field is not None, f"{field_name} field not found in schema"
            assert field.dataType == ArrayType(DoubleType())

    def test_metadata_columns_present(self):
        """Verify all required metadata columns are in schema."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_trips_schema

        field_names = [f.name for f in bronze_trips_schema.fields]

        # Ingestion metadata
        assert "_ingested_at" in field_names
        assert "_kafka_partition" in field_names
        assert "_kafka_offset" in field_names

        # Tracing metadata
        assert "session_id" in field_names
        assert "correlation_id" in field_names
        assert "causation_id" in field_names

    def test_metadata_column_types(self):
        """Verify metadata columns have correct types."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_trips_schema

        ingested_at = next(f for f in bronze_trips_schema.fields if f.name == "_ingested_at")
        assert ingested_at.dataType == TimestampType()
        assert ingested_at.nullable is False

        kafka_partition = next(
            f for f in bronze_trips_schema.fields if f.name == "_kafka_partition"
        )
        assert kafka_partition.dataType == IntegerType()
        assert kafka_partition.nullable is False

        kafka_offset = next(f for f in bronze_trips_schema.fields if f.name == "_kafka_offset")
        assert kafka_offset.dataType == LongType()
        assert kafka_offset.nullable is False

    def test_tracing_column_types(self):
        """Verify tracing columns have correct types (nullable strings)."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_trips_schema

        for field_name in ["session_id", "correlation_id", "causation_id"]:
            field = next(f for f in bronze_trips_schema.fields if f.name == field_name)
            assert field.dataType == StringType()
            assert field.nullable is True

    def test_required_event_fields_present(self):
        """Verify all required event fields are in schema."""
        from schemas.lakehouse.schemas.bronze_tables import bronze_trips_schema

        field_names = [f.name for f in bronze_trips_schema.fields]

        required_fields = [
            "event_id",
            "event_type",
            "timestamp",
            "trip_id",
            "rider_id",
            "pickup_location",
            "dropoff_location",
            "pickup_zone_id",
            "dropoff_zone_id",
            "surge_multiplier",
            "fare",
        ]

        for field_name in required_fields:
            assert field_name in field_names, f"{field_name} not found in schema"
