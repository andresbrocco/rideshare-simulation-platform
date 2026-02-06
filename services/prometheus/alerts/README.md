# Prometheus Alert Rules

This directory will contain Prometheus alert rule files in Phase 5.

## Planned Alert Files

- `simulation_alerts.yml` - Alerts for simulation service health
- `infrastructure_alerts.yml` - Alerts for Kafka, Redis, Spark health
- `system_alerts.yml` - Alerts for system resource usage

## Example Alert Structure

```yaml
groups:
  - name: simulation
    interval: 30s
    rules:
      - alert: HighTripFailureRate
        expr: rate(trips_failed_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High trip failure rate detected"
          description: "Trip failure rate is {{ $value }} trips/sec"
```

## References
- [Prometheus Alerting Rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
