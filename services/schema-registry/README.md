# Schema Registry

> Avro schema management service for Kafka topics - stores, validates, and enforces compatibility for message schemas

## Quick Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `KAFKA_SCHEMA_REGISTRY_URL` | Schema Registry HTTP API URL | `http://schema-registry:8081` | Yes |
| `SCHEMA_REGISTRY_USER` | HTTP Basic Auth username (from Secrets Manager) | `admin` (dev) | Yes |
| `SCHEMA_REGISTRY_PASSWORD` | HTTP Basic Auth password (from Secrets Manager) | `admin` (dev) | Yes |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/subjects` | List all schema subjects (health check) |
| GET | `/subjects/{subject}/versions` | List versions for a subject |
| GET | `/subjects/{subject}/versions/latest` | Get latest schema version |
| POST | `/subjects/{subject}/versions` | Register new schema version |
| GET | `/schemas/ids/{id}` | Get schema by global ID |
| GET | `/config` | Get global compatibility level |

```bash
# List all registered schemas
curl -u admin:admin http://localhost:8085/subjects

# Get latest version of trips schema
curl -u admin:admin http://localhost:8085/subjects/trips-value/versions/latest

# Get schema by ID
curl -u admin:admin http://localhost:8085/schemas/ids/1
```

### Configuration

| File | Purpose |
|------|---------|
| `jaas.conf` | JAAS authentication configuration for HTTP Basic Auth |
| `users.properties` | User credentials file (username:password,role) |

### Kafka Schemas

The platform registers 8 Avro schemas (lazy registration on first produce):

| Schema Subject | Kafka Topic | Schema Location |
|----------------|-------------|-----------------|
| `trips-value` | `trips` | `schemas/kafka/trip_event.json` |
| `gps_pings-value` | `gps_pings` | `schemas/kafka/gps_ping_event.json` |
| `driver_status-value` | `driver_status` | `schemas/kafka/driver_status_event.json` |
| `surge_updates-value` | `surge_updates` | `schemas/kafka/surge_update_event.json` |
| `ratings-value` | `ratings` | `schemas/kafka/rating_event.json` |
| `payments-value` | `payments` | `schemas/kafka/payment_event.json` |
| `driver_profiles-value` | `driver_profiles` | `schemas/kafka/driver_profile_event.json` |
| `rider_profiles-value` | `rider_profiles` | `schemas/kafka/rider_profile_event.json` |

### Prerequisites

- Kafka broker running and healthy (`kafka:29092`)
- LocalStack Secrets Manager seeded with credentials (`rideshare/core`)
- JVM 11+ (included in `confluentinc/cp-schema-registry:7.5.0`)

## Common Tasks

### Check Service Health

```bash
# Via Docker
docker compose -f infrastructure/docker/compose.yml --profile core ps schema-registry

# Via API (requires Basic Auth)
curl -u admin:admin http://localhost:8085/subjects
```

### View Registered Schemas

```bash
# List all subjects
curl -u admin:admin http://localhost:8085/subjects

# Get schema details
curl -u admin:admin http://localhost:8085/subjects/trips-value/versions/latest | jq
```

### Register Schema Manually (Testing)

```bash
# Register a test schema
curl -X POST -u admin:admin \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{"schema": "{\"type\":\"record\",\"name\":\"Test\",\"fields\":[{\"name\":\"field1\",\"type\":\"string\"}]}"}' \
  http://localhost:8085/subjects/test-value/versions
```

### Configure Compatibility Level

```bash
# Get global compatibility
curl -u admin:admin http://localhost:8085/config

# Set subject-specific compatibility (backward, forward, full, none)
curl -X PUT -u admin:admin \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{"compatibility": "BACKWARD"}' \
  http://localhost:8085/config/trips-value
```

### Debug Connection Issues

```bash
# Check if Schema Registry can reach Kafka
docker compose -f infrastructure/docker/compose.yml --profile core logs schema-registry | grep -i "kafka"

# Verify internal `_schemas` topic exists
docker compose -f infrastructure/docker/compose.yml --profile core exec kafka kafka-topics --bootstrap-server localhost:9092 --list | grep _schemas
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `401 Unauthorized` when accessing API | Missing or incorrect Basic Auth credentials | Use `-u admin:admin` or set `KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO` in client |
| Schemas not appearing after simulation start | Lazy registration - schemas only appear on first produce | Start simulation and send trip/GPS events, then check `/subjects` |
| `KAFKASTORE_CONNECTION_FAILED` on startup | Kafka broker not healthy or `kafka-init` not complete | Check `kafka` service health; verify `depends_on: kafka-init` succeeded |
| `_schemas` topic missing | Kafka broker restarted and topic lost (development) | Restart Schema Registry; it will auto-create `_schemas` topic |
| Port 8085 connection refused from host | Schema Registry not started or health check failing | Check `docker compose ps`; review logs for JVM heap or auth config errors |
| Clients get "Subject not found" | Schema not yet registered by producer | Ensure producer has serialized at least one message to the topic |

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context and design decisions
- [../kafka/README.md](../kafka/README.md) — Kafka broker configuration
- [../../schemas/kafka/](../../schemas/kafka/) — JSON Schema definitions for Kafka events
- [../../docs/SECURITY.md](../../docs/SECURITY.md) — Authentication and credential management
