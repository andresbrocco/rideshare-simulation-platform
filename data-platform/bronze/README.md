# Bronze Layer

The Bronze layer stores raw events ingested from Kafka topics with minimal transformation. Data is stored in Delta Lake format on MinIO (S3-compatible storage).

## Schema Design

### Source Alignment
Each Bronze table schema maps directly to a JSON schema in `/schemas/*.json`. Field names and types match the source events exactly to preserve data fidelity.

### Standard Fields

Every Bronze table includes three categories of standard fields:

**Tracing Fields** (nullable)
- `session_id` - Simulation session identifier
- `correlation_id` - Request correlation for distributed tracing
- `causation_id` - ID of the event that caused this event

**Ingestion Metadata** (non-nullable)
- `_ingested_at` - Timestamp when the record was written to Bronze
- `_kafka_partition` - Source Kafka partition number
- `_kafka_offset` - Source Kafka offset for exactly-once processing

## Tables

| Table | Source Topic | Description |
|-------|--------------|-------------|
| `bronze_trips` | trips | Trip lifecycle events (requested, matched, started, completed, cancelled) |
| `bronze_gps_pings` | gps-pings | High-frequency location updates from drivers and riders |
| `bronze_driver_status` | driver-status | Driver availability state changes |
| `bronze_surge_updates` | surge-updates | Zone-level surge pricing calculations |
| `bronze_ratings` | ratings | Post-trip ratings from riders and drivers |
| `bronze_payments` | payments | Payment processing events |
| `bronze_driver_profiles` | driver-profiles | Driver profile creation and updates (SCD Type 2 source) |
| `bronze_rider_profiles` | rider-profiles | Rider profile creation and updates (SCD Type 2 source) |

## Type Mappings

| JSON Schema Type | PySpark Type |
|------------------|--------------|
| string (UUID) | StringType |
| string (ISO timestamp) | TimestampType |
| number | DoubleType |
| integer | IntegerType |
| array of numbers | ArrayType(DoubleType) |
| array of strings | ArrayType(StringType) |
| nested coordinate array | ArrayType(ArrayType(DoubleType)) |

## Usage

```python
from bronze.schemas.bronze_tables import (
    bronze_trips_schema,
    bronze_gps_pings_schema,
    bronze_driver_status_schema,
    bronze_surge_updates_schema,
    bronze_ratings_schema,
    bronze_payments_schema,
    bronze_driver_profiles_schema,
    bronze_rider_profiles_schema,
)

# Read from Kafka with schema
df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "localhost:9092")
    .option("subscribe", "trips")
    .load()
    .select(from_json(col("value").cast("string"), bronze_trips_schema).alias("data"))
    .select("data.*")
)

# Write to Delta
df.writeStream.format("delta").save("s3a://rideshare-bronze/trips")
```

## Storage Location

Bronze tables are stored in the `rideshare-bronze` bucket:
- Local: MinIO at `s3a://rideshare-bronze/<table_name>`
- Production: AWS S3 at `s3://rideshare-bronze/<table_name>`
