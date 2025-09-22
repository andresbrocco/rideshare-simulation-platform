# Databricks Notebooks

This directory contains Databricks notebooks for the Bronze layer of the medallion lakehouse architecture.

## Purpose

Bronze layer notebooks ingest streaming events from Kafka topics and write them to Delta Lake tables in their raw form. Each topic has a corresponding notebook that:

- Connects to Confluent Cloud Kafka
- Reads streaming events with schema validation
- Writes to Delta Lake in append mode
- Maintains event ordering and exactly-once semantics

## Directory Structure

```
databricks/
├── README.md           # This file
├── notebooks/          # Databricks notebooks (.py or .ipynb format)
├── tests/              # Unit tests for notebook logic
├── config/             # Configuration files (connection strings, schemas)
└── utils/              # Shared utility functions
```

## Kafka Topics → Bronze Tables

| Topic | Bronze Table | Description |
|-------|-------------|-------------|
| trips | bronze.trips | Trip state transitions |
| gps-pings | bronze.gps_pings | GPS location pings |
| driver-status | bronze.driver_status | Driver status changes |
| surge-updates | bronze.surge_updates | Surge pricing updates |
| ratings | bronze.ratings | Post-trip ratings |
| payments | bronze.payments | Payment processing events |
| driver-profiles | bronze.driver_profiles | Driver profile creation/updates |
| rider-profiles | bronze.rider_profiles | Rider profile creation/updates |

## Configuration Management

Notebooks use Databricks secrets for sensitive configuration:

- Kafka credentials: `scope: kafka, key: bootstrap_servers, api_key, api_secret`
- Schema Registry: `scope: schema_registry, key: url, api_key, api_secret`

Non-sensitive configs (topic names, checkpoint locations) are stored in `config/` as YAML files.

## Testing Strategy

- Unit tests validate schema transformations and edge cases
- Integration tests verify end-to-end streaming pipeline
- Tests run in Databricks Workflows before deployment

## Deployment

Notebooks sync to Databricks workspace using:
- Databricks CLI for manual deployment
- Terraform for infrastructure-as-code (production)
- Git integration in Databricks Repos for version control

## Development Workflow

1. Develop notebooks locally or in Databricks workspace
2. Test with sample data in development environment
3. Run integration tests in Databricks Workflows
4. Promote to production via Terraform/Git sync
