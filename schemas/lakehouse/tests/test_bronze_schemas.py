"""Tests for Bronze layer PySpark schemas.

These tests verify that Bronze table schemas:
1. Match the JSON schema definitions in schemas/*.json
2. Include required metadata fields for data lineage
3. Include tracing fields for observability
4. Use appropriate PySpark types for each field
"""

import pytest
from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from schemas.lakehouse.schemas.bronze_tables import (
    bronze_driver_profiles_schema,
    bronze_driver_status_schema,
    bronze_gps_pings_schema,
    bronze_payments_schema,
    bronze_ratings_schema,
    bronze_rider_profiles_schema,
    bronze_surge_updates_schema,
    bronze_trips_schema,
)


def get_field_names(schema: StructType) -> set[str]:
    """Extract field names from a PySpark schema."""
    return {field.name for field in schema.fields}


def get_field_type(schema: StructType, field_name: str):
    """Get the data type of a specific field."""
    for field in schema.fields:
        if field.name == field_name:
            return field.dataType
    return None


def get_field(schema: StructType, field_name: str) -> StructField | None:
    """Get a specific field from the schema."""
    for field in schema.fields:
        if field.name == field_name:
            return field
    return None


# Common fields that all Bronze schemas must have
METADATA_FIELDS = {"_ingested_at", "_kafka_partition", "_kafka_offset"}
TRACING_FIELDS = {"session_id", "correlation_id", "causation_id"}


class TestBronzeTripSchema:
    """Verify trip events Bronze schema matches JSON schema with metadata fields."""

    def test_has_required_event_fields(self):
        """Schema has all required fields from trip_event.json."""
        required_fields = {
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
        }
        actual_fields = get_field_names(bronze_trips_schema)
        missing = required_fields - actual_fields
        assert not missing, f"Missing required fields: {missing}"

    def test_has_optional_trip_fields(self):
        """Schema has optional trip fields."""
        optional_fields = {
            "driver_id",
            "offer_sequence",
            "cancelled_by",
            "cancellation_reason",
            "cancellation_stage",
            "route",
            "pickup_route",
            "route_progress_index",
            "pickup_route_progress_index",
        }
        actual_fields = get_field_names(bronze_trips_schema)
        missing = optional_fields - actual_fields
        assert not missing, f"Missing optional fields: {missing}"

    def test_has_metadata_fields(self):
        """Schema has metadata fields for data lineage."""
        actual_fields = get_field_names(bronze_trips_schema)
        missing = METADATA_FIELDS - actual_fields
        assert not missing, f"Missing metadata fields: {missing}"

    def test_has_tracing_fields(self):
        """Schema has tracing fields for observability."""
        actual_fields = get_field_names(bronze_trips_schema)
        missing = TRACING_FIELDS - actual_fields
        assert not missing, f"Missing tracing fields: {missing}"

    def test_event_id_is_string(self):
        """event_id should be StringType for UUID."""
        assert isinstance(get_field_type(bronze_trips_schema, "event_id"), StringType)

    def test_timestamp_is_timestamp_type(self):
        """timestamp should be TimestampType."""
        assert isinstance(get_field_type(bronze_trips_schema, "timestamp"), TimestampType)

    def test_pickup_location_is_array_of_doubles(self):
        """pickup_location should be ArrayType(DoubleType) for [lat, lon]."""
        field_type = get_field_type(bronze_trips_schema, "pickup_location")
        assert isinstance(field_type, ArrayType)
        assert isinstance(field_type.elementType, DoubleType)

    def test_dropoff_location_is_array_of_doubles(self):
        """dropoff_location should be ArrayType(DoubleType) for [lat, lon]."""
        field_type = get_field_type(bronze_trips_schema, "dropoff_location")
        assert isinstance(field_type, ArrayType)
        assert isinstance(field_type.elementType, DoubleType)

    def test_surge_multiplier_is_double(self):
        """surge_multiplier should be DoubleType."""
        assert isinstance(get_field_type(bronze_trips_schema, "surge_multiplier"), DoubleType)

    def test_fare_is_double(self):
        """fare should be DoubleType."""
        assert isinstance(get_field_type(bronze_trips_schema, "fare"), DoubleType)

    def test_offer_sequence_is_integer(self):
        """offer_sequence should be IntegerType."""
        assert isinstance(get_field_type(bronze_trips_schema, "offer_sequence"), IntegerType)

    def test_route_is_nested_array(self):
        """route should be ArrayType(ArrayType(DoubleType)) for coordinates."""
        field_type = get_field_type(bronze_trips_schema, "route")
        assert isinstance(field_type, ArrayType)
        assert isinstance(field_type.elementType, ArrayType)
        assert isinstance(field_type.elementType.elementType, DoubleType)

    def test_pickup_route_is_nested_array(self):
        """pickup_route should be ArrayType(ArrayType(DoubleType))."""
        field_type = get_field_type(bronze_trips_schema, "pickup_route")
        assert isinstance(field_type, ArrayType)
        assert isinstance(field_type.elementType, ArrayType)
        assert isinstance(field_type.elementType.elementType, DoubleType)

    def test_route_progress_index_is_integer(self):
        """route_progress_index should be IntegerType."""
        assert isinstance(get_field_type(bronze_trips_schema, "route_progress_index"), IntegerType)

    def test_ingested_at_is_timestamp(self):
        """_ingested_at metadata field should be TimestampType."""
        assert isinstance(get_field_type(bronze_trips_schema, "_ingested_at"), TimestampType)

    def test_kafka_partition_is_integer(self):
        """_kafka_partition should be IntegerType."""
        assert isinstance(get_field_type(bronze_trips_schema, "_kafka_partition"), IntegerType)

    def test_kafka_offset_is_long(self):
        """_kafka_offset should be LongType for large offset values."""
        assert isinstance(get_field_type(bronze_trips_schema, "_kafka_offset"), LongType)


class TestBronzeGpsPingsSchema:
    """Verify GPS ping Bronze schema handles high-volume streaming."""

    def test_has_required_fields(self):
        """Schema has all required fields from gps_ping_event.json."""
        required_fields = {
            "event_id",
            "entity_type",
            "entity_id",
            "timestamp",
            "location",
            "accuracy",
        }
        actual_fields = get_field_names(bronze_gps_pings_schema)
        missing = required_fields - actual_fields
        assert not missing, f"Missing required fields: {missing}"

    def test_has_optional_fields(self):
        """Schema has optional GPS ping fields."""
        optional_fields = {
            "heading",
            "speed",
            "trip_id",
            "trip_state",
            "route_progress_index",
            "pickup_route_progress_index",
        }
        actual_fields = get_field_names(bronze_gps_pings_schema)
        missing = optional_fields - actual_fields
        assert not missing, f"Missing optional fields: {missing}"

    def test_has_metadata_fields(self):
        """Schema has metadata fields."""
        actual_fields = get_field_names(bronze_gps_pings_schema)
        missing = METADATA_FIELDS - actual_fields
        assert not missing, f"Missing metadata fields: {missing}"

    def test_has_tracing_fields(self):
        """Schema has tracing fields."""
        actual_fields = get_field_names(bronze_gps_pings_schema)
        missing = TRACING_FIELDS - actual_fields
        assert not missing, f"Missing tracing fields: {missing}"

    def test_location_is_array_of_doubles(self):
        """location should be ArrayType(DoubleType) for [lat, lon]."""
        field_type = get_field_type(bronze_gps_pings_schema, "location")
        assert isinstance(field_type, ArrayType)
        assert isinstance(field_type.elementType, DoubleType)

    def test_accuracy_is_double(self):
        """accuracy should be DoubleType."""
        assert isinstance(get_field_type(bronze_gps_pings_schema, "accuracy"), DoubleType)

    def test_heading_is_double(self):
        """heading should be DoubleType."""
        assert isinstance(get_field_type(bronze_gps_pings_schema, "heading"), DoubleType)

    def test_speed_is_double(self):
        """speed should be DoubleType."""
        assert isinstance(get_field_type(bronze_gps_pings_schema, "speed"), DoubleType)

    def test_entity_type_is_string(self):
        """entity_type should be StringType."""
        assert isinstance(get_field_type(bronze_gps_pings_schema, "entity_type"), StringType)

    def test_timestamp_is_timestamp_type(self):
        """timestamp should be TimestampType."""
        assert isinstance(get_field_type(bronze_gps_pings_schema, "timestamp"), TimestampType)


class TestBronzeDriverStatusSchema:
    """Verify driver status Bronze schema."""

    def test_has_required_fields(self):
        """Schema has all required fields from driver_status_event.json."""
        required_fields = {
            "event_id",
            "driver_id",
            "timestamp",
            "new_status",
            "trigger",
            "location",
        }
        actual_fields = get_field_names(bronze_driver_status_schema)
        missing = required_fields - actual_fields
        assert not missing, f"Missing required fields: {missing}"

    def test_has_optional_fields(self):
        """Schema has optional status fields."""
        optional_fields = {"previous_status"}
        actual_fields = get_field_names(bronze_driver_status_schema)
        missing = optional_fields - actual_fields
        assert not missing, f"Missing optional fields: {missing}"

    def test_has_metadata_fields(self):
        """Schema has metadata fields."""
        actual_fields = get_field_names(bronze_driver_status_schema)
        missing = METADATA_FIELDS - actual_fields
        assert not missing, f"Missing metadata fields: {missing}"

    def test_has_tracing_fields(self):
        """Schema has tracing fields."""
        actual_fields = get_field_names(bronze_driver_status_schema)
        missing = TRACING_FIELDS - actual_fields
        assert not missing, f"Missing tracing fields: {missing}"

    def test_location_is_array_of_doubles(self):
        """location should be ArrayType(DoubleType)."""
        field_type = get_field_type(bronze_driver_status_schema, "location")
        assert isinstance(field_type, ArrayType)
        assert isinstance(field_type.elementType, DoubleType)

    def test_new_status_is_string(self):
        """new_status should be StringType."""
        assert isinstance(get_field_type(bronze_driver_status_schema, "new_status"), StringType)

    def test_trigger_is_string(self):
        """trigger should be StringType."""
        assert isinstance(get_field_type(bronze_driver_status_schema, "trigger"), StringType)

    def test_timestamp_is_timestamp_type(self):
        """timestamp should be TimestampType."""
        assert isinstance(get_field_type(bronze_driver_status_schema, "timestamp"), TimestampType)


class TestBronzeSurgeUpdatesSchema:
    """Verify surge updates schema."""

    def test_has_required_fields(self):
        """Schema has all required fields from surge_update_event.json."""
        required_fields = {
            "event_id",
            "zone_id",
            "timestamp",
            "previous_multiplier",
            "new_multiplier",
            "available_drivers",
            "pending_requests",
        }
        actual_fields = get_field_names(bronze_surge_updates_schema)
        missing = required_fields - actual_fields
        assert not missing, f"Missing required fields: {missing}"

    def test_has_optional_fields(self):
        """Schema has optional surge fields."""
        optional_fields = {"calculation_window_seconds"}
        actual_fields = get_field_names(bronze_surge_updates_schema)
        missing = optional_fields - actual_fields
        assert not missing, f"Missing optional fields: {missing}"

    def test_has_metadata_fields(self):
        """Schema has metadata fields."""
        actual_fields = get_field_names(bronze_surge_updates_schema)
        missing = METADATA_FIELDS - actual_fields
        assert not missing, f"Missing metadata fields: {missing}"

    def test_has_tracing_fields(self):
        """Schema has tracing fields."""
        actual_fields = get_field_names(bronze_surge_updates_schema)
        missing = TRACING_FIELDS - actual_fields
        assert not missing, f"Missing tracing fields: {missing}"

    def test_available_drivers_is_integer(self):
        """available_drivers should be IntegerType."""
        assert isinstance(
            get_field_type(bronze_surge_updates_schema, "available_drivers"),
            IntegerType,
        )

    def test_pending_requests_is_integer(self):
        """pending_requests should be IntegerType."""
        assert isinstance(
            get_field_type(bronze_surge_updates_schema, "pending_requests"), IntegerType
        )

    def test_previous_multiplier_is_double(self):
        """previous_multiplier should be DoubleType."""
        assert isinstance(
            get_field_type(bronze_surge_updates_schema, "previous_multiplier"),
            DoubleType,
        )

    def test_new_multiplier_is_double(self):
        """new_multiplier should be DoubleType."""
        assert isinstance(get_field_type(bronze_surge_updates_schema, "new_multiplier"), DoubleType)

    def test_calculation_window_seconds_is_integer(self):
        """calculation_window_seconds should be IntegerType."""
        assert isinstance(
            get_field_type(bronze_surge_updates_schema, "calculation_window_seconds"),
            IntegerType,
        )

    def test_timestamp_is_timestamp_type(self):
        """timestamp should be TimestampType."""
        assert isinstance(get_field_type(bronze_surge_updates_schema, "timestamp"), TimestampType)


class TestBronzeRatingsSchema:
    """Verify ratings schema."""

    def test_has_required_fields(self):
        """Schema has all required fields from rating_event.json."""
        required_fields = {
            "event_id",
            "trip_id",
            "timestamp",
            "rater_type",
            "rater_id",
            "ratee_type",
            "ratee_id",
            "rating",
        }
        actual_fields = get_field_names(bronze_ratings_schema)
        missing = required_fields - actual_fields
        assert not missing, f"Missing required fields: {missing}"

    def test_has_metadata_fields(self):
        """Schema has metadata fields."""
        actual_fields = get_field_names(bronze_ratings_schema)
        missing = METADATA_FIELDS - actual_fields
        assert not missing, f"Missing metadata fields: {missing}"

    def test_has_tracing_fields(self):
        """Schema has tracing fields."""
        actual_fields = get_field_names(bronze_ratings_schema)
        missing = TRACING_FIELDS - actual_fields
        assert not missing, f"Missing tracing fields: {missing}"

    def test_rating_is_integer(self):
        """rating should be IntegerType for 1-5 stars."""
        assert isinstance(get_field_type(bronze_ratings_schema, "rating"), IntegerType)

    def test_rater_type_is_string(self):
        """rater_type should be StringType."""
        assert isinstance(get_field_type(bronze_ratings_schema, "rater_type"), StringType)

    def test_ratee_type_is_string(self):
        """ratee_type should be StringType."""
        assert isinstance(get_field_type(bronze_ratings_schema, "ratee_type"), StringType)

    def test_timestamp_is_timestamp_type(self):
        """timestamp should be TimestampType."""
        assert isinstance(get_field_type(bronze_ratings_schema, "timestamp"), TimestampType)


class TestBronzePaymentsSchema:
    """Verify payments schema."""

    def test_has_required_fields(self):
        """Schema has all required fields from payment_event.json."""
        required_fields = {
            "event_id",
            "payment_id",
            "trip_id",
            "timestamp",
            "rider_id",
            "driver_id",
            "payment_method_type",
            "payment_method_masked",
            "fare_amount",
            "platform_fee_percentage",
            "platform_fee_amount",
            "driver_payout_amount",
        }
        actual_fields = get_field_names(bronze_payments_schema)
        missing = required_fields - actual_fields
        assert not missing, f"Missing required fields: {missing}"

    def test_has_metadata_fields(self):
        """Schema has metadata fields."""
        actual_fields = get_field_names(bronze_payments_schema)
        missing = METADATA_FIELDS - actual_fields
        assert not missing, f"Missing metadata fields: {missing}"

    def test_has_tracing_fields(self):
        """Schema has tracing fields."""
        actual_fields = get_field_names(bronze_payments_schema)
        missing = TRACING_FIELDS - actual_fields
        assert not missing, f"Missing tracing fields: {missing}"

    def test_fare_amount_is_double(self):
        """fare_amount should be DoubleType."""
        assert isinstance(get_field_type(bronze_payments_schema, "fare_amount"), DoubleType)

    def test_platform_fee_percentage_is_double(self):
        """platform_fee_percentage should be DoubleType."""
        assert isinstance(
            get_field_type(bronze_payments_schema, "platform_fee_percentage"),
            DoubleType,
        )

    def test_platform_fee_amount_is_double(self):
        """platform_fee_amount should be DoubleType."""
        assert isinstance(get_field_type(bronze_payments_schema, "platform_fee_amount"), DoubleType)

    def test_driver_payout_amount_is_double(self):
        """driver_payout_amount should be DoubleType."""
        assert isinstance(
            get_field_type(bronze_payments_schema, "driver_payout_amount"), DoubleType
        )

    def test_payment_method_type_is_string(self):
        """payment_method_type should be StringType."""
        assert isinstance(get_field_type(bronze_payments_schema, "payment_method_type"), StringType)

    def test_timestamp_is_timestamp_type(self):
        """timestamp should be TimestampType."""
        assert isinstance(get_field_type(bronze_payments_schema, "timestamp"), TimestampType)


class TestBronzeDriverProfilesSchema:
    """Verify driver profile schema supports SCD Type 2 preparation."""

    def test_has_required_fields(self):
        """Schema has all required fields from driver_profile_event.json."""
        required_fields = {
            "event_id",
            "event_type",
            "driver_id",
            "timestamp",
            "first_name",
            "last_name",
            "email",
            "phone",
            "home_location",
            "shift_preference",
            "vehicle_make",
            "vehicle_model",
            "vehicle_year",
            "license_plate",
        }
        actual_fields = get_field_names(bronze_driver_profiles_schema)
        missing = required_fields - actual_fields
        assert not missing, f"Missing required fields: {missing}"

    def test_has_metadata_fields(self):
        """Schema has metadata fields."""
        actual_fields = get_field_names(bronze_driver_profiles_schema)
        missing = METADATA_FIELDS - actual_fields
        assert not missing, f"Missing metadata fields: {missing}"

    def test_has_tracing_fields(self):
        """Schema has tracing fields."""
        actual_fields = get_field_names(bronze_driver_profiles_schema)
        missing = TRACING_FIELDS - actual_fields
        assert not missing, f"Missing tracing fields: {missing}"

    def test_event_type_is_string(self):
        """event_type should be StringType for driver.created/driver.updated."""
        assert isinstance(get_field_type(bronze_driver_profiles_schema, "event_type"), StringType)

    def test_home_location_is_array_of_doubles(self):
        """home_location should be ArrayType(DoubleType)."""
        field_type = get_field_type(bronze_driver_profiles_schema, "home_location")
        assert isinstance(field_type, ArrayType)
        assert isinstance(field_type.elementType, DoubleType)

    def test_vehicle_year_is_integer(self):
        """vehicle_year should be IntegerType."""
        assert isinstance(
            get_field_type(bronze_driver_profiles_schema, "vehicle_year"), IntegerType
        )

    def test_shift_preference_is_string(self):
        """shift_preference should be StringType."""
        assert isinstance(
            get_field_type(bronze_driver_profiles_schema, "shift_preference"),
            StringType,
        )

    def test_timestamp_is_timestamp_type(self):
        """timestamp should be TimestampType."""
        assert isinstance(get_field_type(bronze_driver_profiles_schema, "timestamp"), TimestampType)


class TestBronzeRiderProfilesSchema:
    """Verify rider profile schema."""

    def test_has_required_fields(self):
        """Schema has all required fields from rider_profile_event.json."""
        required_fields = {
            "event_id",
            "event_type",
            "rider_id",
            "timestamp",
            "first_name",
            "last_name",
            "email",
            "phone",
            "home_location",
            "payment_method_type",
            "payment_method_masked",
        }
        actual_fields = get_field_names(bronze_rider_profiles_schema)
        missing = required_fields - actual_fields
        assert not missing, f"Missing required fields: {missing}"

    def test_has_optional_fields(self):
        """Schema has optional rider profile fields."""
        optional_fields = {"behavior_factor"}
        actual_fields = get_field_names(bronze_rider_profiles_schema)
        missing = optional_fields - actual_fields
        assert not missing, f"Missing optional fields: {missing}"

    def test_has_metadata_fields(self):
        """Schema has metadata fields."""
        actual_fields = get_field_names(bronze_rider_profiles_schema)
        missing = METADATA_FIELDS - actual_fields
        assert not missing, f"Missing metadata fields: {missing}"

    def test_has_tracing_fields(self):
        """Schema has tracing fields."""
        actual_fields = get_field_names(bronze_rider_profiles_schema)
        missing = TRACING_FIELDS - actual_fields
        assert not missing, f"Missing tracing fields: {missing}"

    def test_event_type_is_string(self):
        """event_type should be StringType for rider.created/rider.updated."""
        assert isinstance(get_field_type(bronze_rider_profiles_schema, "event_type"), StringType)

    def test_home_location_is_array_of_doubles(self):
        """home_location should be ArrayType(DoubleType)."""
        field_type = get_field_type(bronze_rider_profiles_schema, "home_location")
        assert isinstance(field_type, ArrayType)
        assert isinstance(field_type.elementType, DoubleType)

    def test_behavior_factor_is_double(self):
        """behavior_factor should be DoubleType."""
        assert isinstance(
            get_field_type(bronze_rider_profiles_schema, "behavior_factor"), DoubleType
        )

    def test_payment_method_type_is_string(self):
        """payment_method_type should be StringType."""
        assert isinstance(
            get_field_type(bronze_rider_profiles_schema, "payment_method_type"),
            StringType,
        )

    def test_timestamp_is_timestamp_type(self):
        """timestamp should be TimestampType."""
        assert isinstance(get_field_type(bronze_rider_profiles_schema, "timestamp"), TimestampType)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
