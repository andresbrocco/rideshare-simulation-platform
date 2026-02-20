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


def _tracing_fields() -> list[StructField]:
    return [
        StructField("session_id", StringType(), True),
        StructField("correlation_id", StringType(), True),
        StructField("causation_id", StringType(), True),
    ]


def _metadata_fields() -> list[StructField]:
    return [
        StructField("_ingested_at", TimestampType(), False),
        StructField("_kafka_partition", IntegerType(), False),
        StructField("_kafka_offset", LongType(), False),
    ]


bronze_trips_schema = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("event_type", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("trip_id", StringType(), False),
        StructField("rider_id", StringType(), False),
        StructField("pickup_location", ArrayType(DoubleType()), False),
        StructField("dropoff_location", ArrayType(DoubleType()), False),
        StructField("pickup_zone_id", StringType(), False),
        StructField("dropoff_zone_id", StringType(), False),
        StructField("surge_multiplier", DoubleType(), False),
        StructField("fare", DoubleType(), False),
        StructField("driver_id", StringType(), True),
        StructField("offer_sequence", IntegerType(), True),
        StructField("cancelled_by", StringType(), True),
        StructField("cancellation_reason", StringType(), True),
        StructField("cancellation_stage", StringType(), True),
        StructField("route", ArrayType(ArrayType(DoubleType())), True),
        StructField("pickup_route", ArrayType(ArrayType(DoubleType())), True),
        StructField("route_progress_index", IntegerType(), True),
        StructField("pickup_route_progress_index", IntegerType(), True),
        *_tracing_fields(),
        *_metadata_fields(),
    ]
)

bronze_gps_pings_schema = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("entity_type", StringType(), False),
        StructField("entity_id", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("location", ArrayType(DoubleType()), False),
        StructField("accuracy", DoubleType(), False),
        StructField("heading", DoubleType(), True),
        StructField("speed", DoubleType(), True),
        StructField("trip_id", StringType(), True),
        StructField("trip_state", StringType(), True),
        StructField("route_progress_index", IntegerType(), True),
        StructField("pickup_route_progress_index", IntegerType(), True),
        *_tracing_fields(),
        *_metadata_fields(),
    ]
)

bronze_driver_status_schema = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("driver_id", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("new_status", StringType(), False),
        StructField("trigger", StringType(), False),
        StructField("location", ArrayType(DoubleType()), False),
        StructField("previous_status", StringType(), True),
        *_tracing_fields(),
        *_metadata_fields(),
    ]
)

bronze_surge_updates_schema = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("zone_id", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("previous_multiplier", DoubleType(), False),
        StructField("new_multiplier", DoubleType(), False),
        StructField("available_drivers", IntegerType(), False),
        StructField("pending_requests", IntegerType(), False),
        StructField("calculation_window_seconds", IntegerType(), True),
        *_tracing_fields(),
        *_metadata_fields(),
    ]
)

bronze_ratings_schema = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("trip_id", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("rater_type", StringType(), False),
        StructField("rater_id", StringType(), False),
        StructField("ratee_type", StringType(), False),
        StructField("ratee_id", StringType(), False),
        StructField("rating", IntegerType(), False),
        *_tracing_fields(),
        *_metadata_fields(),
    ]
)

bronze_payments_schema = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("payment_id", StringType(), False),
        StructField("trip_id", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("rider_id", StringType(), False),
        StructField("driver_id", StringType(), False),
        StructField("payment_method_type", StringType(), False),
        StructField("payment_method_masked", StringType(), False),
        StructField("fare_amount", DoubleType(), False),
        StructField("platform_fee_percentage", DoubleType(), False),
        StructField("platform_fee_amount", DoubleType(), False),
        StructField("driver_payout_amount", DoubleType(), False),
        *_tracing_fields(),
        *_metadata_fields(),
    ]
)

bronze_driver_profiles_schema = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("event_type", StringType(), False),
        StructField("driver_id", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("first_name", StringType(), False),
        StructField("last_name", StringType(), False),
        StructField("email", StringType(), False),
        StructField("phone", StringType(), False),
        StructField("home_location", ArrayType(DoubleType()), False),
        StructField("shift_preference", StringType(), False),
        StructField("vehicle_make", StringType(), False),
        StructField("vehicle_model", StringType(), False),
        StructField("vehicle_year", IntegerType(), False),
        StructField("license_plate", StringType(), False),
        *_tracing_fields(),
        *_metadata_fields(),
    ]
)

bronze_rider_profiles_schema = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("event_type", StringType(), False),
        StructField("rider_id", StringType(), False),
        StructField("timestamp", TimestampType(), False),
        StructField("first_name", StringType(), False),
        StructField("last_name", StringType(), False),
        StructField("email", StringType(), False),
        StructField("phone", StringType(), False),
        StructField("home_location", ArrayType(DoubleType()), False),
        StructField("payment_method_type", StringType(), False),
        StructField("payment_method_masked", StringType(), False),
        StructField("behavior_factor", DoubleType(), True),
        *_tracing_fields(),
        *_metadata_fields(),
    ]
)
