# Grafana Dashboard Files

This directory will contain Grafana dashboard JSON exports in Phase 5.

## Dashboard Organization

Dashboards are organized by category:
- `simulation-*.json` - Simulation service dashboards
- `infrastructure-*.json` - Infrastructure monitoring dashboards
- `business-*.json` - Business metrics dashboards
- `system-*.json` - System resource dashboards

## Adding Dashboards

1. Create/edit dashboard in Grafana UI
2. Export dashboard as JSON
3. Save to this directory with descriptive name
4. Update `provisioning/dashboards/dashboards.yml` to include the file

## Example Dashboard Files

- `simulation-trip-overview.json` - Trip metrics and states
- `infrastructure-kafka.json` - Kafka broker and topic metrics
- `business-revenue.json` - Revenue and payment metrics
- `system-resources.json` - CPU, memory, disk, network
