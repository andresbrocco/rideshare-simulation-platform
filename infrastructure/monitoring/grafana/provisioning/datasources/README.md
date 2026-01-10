# Grafana Datasource Provisioning

This directory will contain Grafana datasource provisioning files in Phase 5.

## Purpose

Datasource provisioning allows automatic configuration of Prometheus as a Grafana datasource.

## Example Configuration

`prometheus-datasource.yml`:
```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
```

## References
- [Grafana Datasource Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/#data-sources)
