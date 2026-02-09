# Confluent Schema Registry

Confluent Schema Registry 7.5.0 for Avro schema management across Kafka topics.

## Purpose

Stock Confluent Schema Registry image with all configuration via environment variables in `compose.yml`. No configuration files exist in this directory — it serves as a documentation anchor in the service tree.

## Configuration

| Setting | Value |
|---------|-------|
| Image | `confluentinc/cp-schema-registry:7.5.0` |
| Port | `8085` (mapped to container port `8081`) |
| Memory | `256MB` heap (`128m`-`256m`) |
| Kafka Connection | `kafka:29092` |
| Config Files | None (env-var configuration in `compose.yml`) |

## Usage

### Start Schema Registry

```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d schema-registry
```

### Health Check / List Subjects

```bash
curl http://localhost:8085/subjects
```

### Get Latest Schema for a Subject

```bash
curl http://localhost:8085/subjects/trips-value/versions/latest
```

### List All Schema Types

```bash
curl http://localhost:8085/schemas/types
```

### Get Schema by ID

```bash
curl http://localhost:8085/schemas/ids/1
```

### View Logs

```bash
docker compose -f infrastructure/docker/compose.yml --profile core logs -f schema-registry
```

## Troubleshooting

**No subjects returned**: Schemas are registered lazily when producers first serialize to a topic. Start the simulation service and produce some events before querying subjects.

**Schema Registry fails to start**: Verify that Kafka is healthy and `kafka-init` completed successfully:
```bash
docker compose -f infrastructure/docker/compose.yml --profile core ps kafka kafka-init
```

**Connection refused on port 8085**: Check that the container is running and the port mapping is active:
```bash
docker compose -f infrastructure/docker/compose.yml --profile core ps schema-registry
```

**Schema compatibility errors**: Schema Registry enforces backward compatibility by default. If a schema change breaks compatibility, check the Avro schema definitions in `schemas/kafka/` and review the [Confluent compatibility documentation](https://docs.confluent.io/platform/7.5/schema-registry/fundamentals/schema-evolution.html).

## References

- [Confluent Schema Registry Documentation](https://docs.confluent.io/platform/7.5/schema-registry/index.html)
- [Schema Registry API Reference](https://docs.confluent.io/platform/7.5/schema-registry/develop/api.html)
- [Schema Evolution and Compatibility](https://docs.confluent.io/platform/7.5/schema-registry/fundamentals/schema-evolution.html)
