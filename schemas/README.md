# Schemas

> Cross-service data contract definitions for Kafka events, Bronze lakehouse PySpark schemas, and the simulation REST/WebSocket API.

## Quick Reference

### Configuration Files

| File | Purpose |
|------|---------|
| `schemas/kafka/*.json` | JSON Schema Draft 2020-12 documents for Kafka event validation via Schema Registry |
| `schemas/api/openapi.json` | OpenAPI 3.1.0 specification for the simulation REST/WebSocket API |
| `schemas/lakehouse/config/delta_config.py` | Delta Lake table property utilities (CDC, auto-optimize, auto-compact) |
| `schemas/lakehouse/pyproject.toml` | Standalone `lakehouse-schemas` package definition |

### Kafka Event Schemas

All schemas live in `schemas/kafka/`. Each event carries three distributed-tracing fields: `session_id`, `correlation_id`, and `causation_id`.

| Schema File | Kafka Topic (inferred) | Key Fields |
|-------------|----------------------|------------|
| `trip_event.json` | `trips` | `event_type` (11 values), `trip_id`, `rider_id`, `driver_id`, `fare`, `surge_multiplier` |
| `driver_status_event.json` | `driver-status` | `driver_id`, `new_status` (`available`, `offline`, `en_route_pickup`, `on_trip`), `trigger`, `location` |
| `gps_ping_event.json` | `gps-pings` | `entity_type` (`driver`/`rider`), `entity_id`, `location`, `route_progress_index`, `pickup_route_progress_index` |
| `driver_profile_event.json` | `driver-profiles` | `event_type` (`driver.created`/`driver.updated`), `driver_id`, `shift_preference`, vehicle fields |
| `rider_profile_event.json` | `rider-profiles` | `event_type` (`rider.created`/`rider.updated`), `rider_id`, `behavior_factor` (created only) |
| `payment_event.json` | `payments` | `payment_id`, `trip_id`, `fare_amount`, `platform_fee_percentage` (decimal 0–1), `driver_payout_amount` |
| `rating_event.json` | `ratings` | `trip_id`, `rater_type`, `ratee_type`, `rating` (1–5) |
| `surge_update_event.json` | `surge-updates` | `zone_id`, `previous_multiplier`, `new_multiplier`, `available_drivers`, `pending_requests` |

### Trip Event Types

```
trip.requested         → trip.offer_sent       → trip.driver_assigned
trip.driver_assigned   → trip.en_route_pickup  → trip.at_pickup
trip.at_pickup         → trip.in_transit       → trip.completed
                                                → trip.cancelled
trip.offer_sent        → trip.offer_expired
                       → trip.offer_rejected
trip.requested         → trip.no_drivers_available
```

### Bronze Delta Tables

Defined in `schemas/lakehouse/scripts/enable_delta_features.py`:

| Table Path | Description |
|-----------|-------------|
| `s3a://rideshare-bronze/bronze_trips/` | Trip state transition events |
| `s3a://rideshare-bronze/bronze_gps_pings/` | GPS location pings |
| `s3a://rideshare-bronze/bronze_driver_status/` | Driver status changes |
| `s3a://rideshare-bronze/bronze_surge_updates/` | Surge pricing updates |
| `s3a://rideshare-bronze/bronze_ratings/` | Post-trip ratings |
| `s3a://rideshare-bronze/bronze_payments/` | Payment processing events |
| `s3a://rideshare-bronze/bronze_driver_profiles/` | Driver profile create/update |
| `s3a://rideshare-bronze/bronze_rider_profiles/` | Rider profile create/update |

All Bronze tables are partitioned by `_ingestion_date` (`yyyy-MM-dd`).

### DLQ Table Schema

The dead-letter queue (`bronze_dlq`) captures failed ingestion events:

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `error_message` | String | No | Error description |
| `error_type` | String | No | Exception class name |
| `original_payload` | String | No | Raw JSON that failed |
| `kafka_topic` | String | No | Source Kafka topic |
| `_kafka_partition` | Integer | No | Kafka partition number |
| `_kafka_offset` | Long | No | Kafka offset |
| `_ingested_at` | Timestamp | No | Ingestion timestamp |
| `session_id` | String | Yes | Simulation run ID |
| `correlation_id` | String | Yes | Primary business entity ID |
| `causation_id` | String | Yes | ID of triggering event |

### Commands

#### Enable Delta Features on All Bronze Tables

Run after Bronze tables exist and contain data:

```bash
cd schemas/lakehouse
./venv/bin/python3 -m schemas.lakehouse.scripts.enable_delta_features
```

This enables Change Data Feed, `autoOptimize.optimizeWrite`, and `autoOptimize.autoCompact` on all 8 Bronze tables.

#### Install `lakehouse-schemas` Package into a PySpark Environment

```bash
cd schemas/lakehouse
pip install -e .
```

#### Verify Delta Table Properties

```sql
-- Check features are enabled on a Bronze table
SELECT key, value
FROM (SHOW TBLPROPERTIES delta.`s3a://rideshare-bronze/bronze_trips/`)
WHERE key IN (
  'delta.enableChangeDataFeed',
  'delta.autoOptimize.optimizeWrite',
  'delta.autoOptimize.autoCompact'
);
```

## Common Tasks

### Validate a Kafka Event Against Its Schema

```python
import json
import jsonschema

with open("schemas/kafka/trip_event.json") as f:
    schema = json.load(f)

event = {
    "event_id": "...",
    "event_type": "trip.completed",
    "timestamp": "2026-01-12T10:00:00Z",
    "trip_id": "...",
    "rider_id": "...",
    "pickup_location": [-23.5, -46.6],
    "dropoff_location": [-23.6, -46.7],
    "pickup_zone_id": "zone-1",
    "dropoff_zone_id": "zone-2",
    "surge_multiplier": 1.2,
    "fare": 18.50
}

jsonschema.validate(event, schema)
```

### Query Bronze CDC Feed

```sql
-- Get all inserts since version 0
SELECT *
FROM table_changes('delta.`s3a://rideshare-bronze/bronze_trips/`', 0)
WHERE _change_type = 'insert'
ORDER BY _commit_version;

-- Get changes in a time range
SELECT *
FROM table_changes('delta.`s3a://rideshare-bronze/bronze_trips/`',
  '2026-01-12 00:00:00', '2026-01-13 00:00:00');
```

### Query a Bronze Table by Date Partition

```sql
-- Efficient date-range query using partition pruning
SELECT * FROM bronze_trips
WHERE _ingestion_date BETWEEN '2026-01-12' AND '2026-01-13';
```

### Replay DLQ Messages

Query the DLQ for failed events to diagnose ingestion failures:

```sql
SELECT kafka_topic, error_type, COUNT(*) as failures, MIN(_ingested_at) as first_seen
FROM bronze_dlq
GROUP BY kafka_topic, error_type
ORDER BY failures DESC;
```

## Troubleshooting

**`DeltaConfig` fails with "No active SparkSession"**: `DeltaConfig` requires a live `SparkSession`. It cannot be called outside a Spark context. Pass a `SparkSession` instance explicitly.

**`enable_delta_features.py` fails with "table not found"**: The Bronze tables must exist before running the script. Tables are created by `bronze-ingestion` on first data arrival — wait until the ingestion service has written at least one batch.

**`behavior_factor` missing from `rider_profile_event`**: This field is only present on `rider.created` events, not `rider.updated`. Treat it as optional in all consumers.

**`platform_fee_percentage` appears to be wrong**: This field is a decimal fraction (e.g., `0.25` for 25%), not an integer percentage. `fare_amount = platform_fee_amount + driver_payout_amount` always holds.

**Both `route_progress_index` and `pickup_route_progress_index` present in GPS ping**: This is expected when a driver is en route to pick up a rider — both fields can be non-null simultaneously.

## Prerequisites

- **Kafka / Schema Registry**: Schemas in `schemas/kafka/` are registered with Confluent Schema Registry at `http://localhost:8085` (local) via the `schema-registry` Docker service.
- **PySpark**: `schemas/lakehouse/` requires PySpark and the `delta` Python package. Install via `schemas/lakehouse/pyproject.toml`.
- **Active Bronze tables**: Delta feature scripts require tables to exist at their S3/MinIO paths before running.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context and non-obvious schema gotchas
- [schemas/kafka/CONTEXT.md](kafka/CONTEXT.md) — Kafka schema details
- [schemas/lakehouse/CONTEXT.md](lakehouse/CONTEXT.md) — Lakehouse schema details
- [schemas/lakehouse/DELTA_FEATURES.md](lakehouse/DELTA_FEATURES.md) — Delta Lake feature reference
- [services/bronze-ingestion/README.md](../services/bronze-ingestion/README.md) — Bronze table creation and ingestion
- [services/stream-processor/README.md](../services/stream-processor/README.md) — Kafka event consumers
