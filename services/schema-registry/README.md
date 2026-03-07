# Schema Registry

> Confluent Schema Registry 7.5.0 — validates and stores JSON Schema definitions for all Kafka event types in the rideshare simulation platform.

## Quick Reference

### Port

| Host Port | Container Port | Protocol |
|-----------|----------------|----------|
| 8085      | 8081           | HTTP     |

### Authentication

Schema Registry requires HTTP Basic Auth for all requests. Credentials are seeded via LocalStack Secrets Manager into `/secrets/core.env` at container startup.

| Secret Key              | Secret Path      | Description                          |
|-------------------------|------------------|--------------------------------------|
| `SCHEMA_REGISTRY_USER`  | `rideshare/core` | Basic auth username for API access   |
| `SCHEMA_REGISTRY_PASSWORD` | `rideshare/core` | Basic auth password for API access |

Default local credentials: `admin` / `admin`

### Configuration Files

| File | Mounted At | Purpose |
|------|-----------|---------|
| `services/schema-registry/jaas.conf` | `/etc/schema-registry/jaas.conf` | Jetty JAAS login config (maps `SchemaRegistry` realm to `users.properties`) |
| `services/schema-registry/users.properties` | `/etc/schema-registry/users.properties` | HTTP Basic Auth user definitions (`admin: admin,admin`) |

### Environment Variables (Docker)

Set by `infrastructure/docker/compose.yml` — not overridable via `.env`:

| Variable | Value | Description |
|----------|-------|-------------|
| `SCHEMA_REGISTRY_HOST_NAME` | `schema-registry` | Container hostname |
| `SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS` | `kafka:29092` | Kafka bootstrap for `_schemas` topic |
| `SCHEMA_REGISTRY_LISTENERS` | `http://0.0.0.0:8081` | HTTP listener |
| `SCHEMA_REGISTRY_KAFKASTORE_SECURITY_PROTOCOL` | `SASL_PLAINTEXT` | Kafka auth protocol |
| `SCHEMA_REGISTRY_KAFKASTORE_SASL_MECHANISM` | `PLAIN` | Kafka SASL mechanism |
| `SCHEMA_REGISTRY_AUTHENTICATION_METHOD` | `BASIC` | HTTP auth method |
| `SCHEMA_REGISTRY_AUTHENTICATION_ROLES` | `admin` | Required role for API access |
| `SCHEMA_REGISTRY_AUTHENTICATION_REALM` | `SchemaRegistry` | JAAS realm name (must match `jaas.conf`) |
| `SCHEMA_REGISTRY_OPTS` | `-Djava.security.auth.login.config=...` | Points JVM to JAAS config |
| `SCHEMA_REGISTRY_HEAP_OPTS` | `-Xms128m -Xmx256m` | JVM heap bounds |

`SCHEMA_REGISTRY_KAFKASTORE_SASL_JAAS_CONFIG` is injected at runtime from `/secrets/core.env` using `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD`.

### Docker Compose Profiles

Schema Registry starts under the `core` and `data-pipeline` profiles:

```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d schema-registry
```

### Depends On

- `secrets-init` — must complete before container starts (provides `/secrets/core.env`)
- `kafka-init` — Kafka topics (including `_schemas`) must exist before Schema Registry connects

### Health Check

```bash
curl -f -u admin:admin http://localhost:8085/subjects
```

The Docker health check polls this endpoint every 10s with up to 12 retries (2-minute window).

---

## Common Tasks

### List All Registered Subjects

```bash
curl -s -u admin:admin http://localhost:8085/subjects | python3 -m json.tool
```

### Fetch Latest Schema for a Subject

```bash
curl -s -u admin:admin http://localhost:8085/subjects/trip_event-value/versions/latest | python3 -m json.tool
```

### Register a New Schema Manually

```bash
curl -s -X POST \
  -u admin:admin \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d '{"schemaType": "JSON", "schema": "{\"type\":\"object\"}"}' \
  http://localhost:8085/subjects/my_topic-value/versions
```

### Check Compatibility Mode

```bash
curl -s -u admin:admin http://localhost:8085/config | python3 -m json.tool
```

### View All Versions of a Subject

```bash
curl -s -u admin:admin http://localhost:8085/subjects/driver_status_event-value/versions
```

---

## Registered Schemas

Schemas are defined in `schemas/kafka/` and auto-registered by the simulation service at startup via `SerializerRegistry`. Eight event types are registered:

| Subject (inferred `-value`) | Source File |
|-----------------------------|-------------|
| `driver_profile_event` | `schemas/kafka/driver_profile_event.json` |
| `driver_status_event` | `schemas/kafka/driver_status_event.json` |
| `gps_ping_event` | `schemas/kafka/gps_ping_event.json` |
| `trip_event` | `schemas/kafka/trip_event.json` |
| `payment_event` | `schemas/kafka/payment_event.json` |
| `rating_event` | `schemas/kafka/rating_event.json` |
| `rider_profile_event` | `schemas/kafka/rider_profile_event.json` |
| `surge_update_event` | `schemas/kafka/surge_update_event.json` |

Schemas are registered with type `JSON`. Schema files are mounted into the simulation container at `/app/schemas`.

---

## Troubleshooting

**Container fails to start / unhealthy**

Check that Kafka is healthy first — Schema Registry depends on `kafka-init` completing. Verify with:
```bash
docker compose -f infrastructure/docker/compose.yml logs schema-registry
```

**`401 Unauthorized` on API requests**

Ensure you are passing `-u admin:admin` (or the correct `SCHEMA_REGISTRY_USER`/`SCHEMA_REGISTRY_PASSWORD` from `rideshare/core` secret). The `BASIC` auth method is enforced for all endpoints.

**`Schema not found` errors in simulation logs**

Schema registration happens during simulation startup via `SerializerRegistry.initialize()`. If Schema Registry was not healthy when the simulation container started, schemas may not be registered. Restart the simulation container after Schema Registry becomes healthy.

**`_schemas` topic connection errors**

Schema Registry connects to Kafka over SASL_PLAINTEXT on `kafka:29092`. If Kafka SASL credentials changed, the `SCHEMA_REGISTRY_KAFKASTORE_SASL_JAAS_CONFIG` (injected from `/secrets/core.env`) must be updated and the container restarted.

---

## Related

- [schemas/kafka/CONTEXT.md](../../schemas/kafka/CONTEXT.md) — JSON Schema definitions for all event types
- [services/kafka/README.md](../kafka/README.md) — Kafka broker; Schema Registry depends on `kafka-init`
- [services/simulation/src/kafka/CONTEXT.md](../simulation/src/kafka/CONTEXT.md) — Producer that registers schemas at startup
- [services/stream-processor/CONTEXT.md](../stream-processor/CONTEXT.md) — Consumer that deserializes validated events
