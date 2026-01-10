# Grafana Dashboard Provisioning

This directory will contain Grafana dashboard provisioning files in Phase 5.

## Purpose

Dashboard provisioning allows automatic loading of dashboards from JSON files.

## Example Configuration

`dashboards.yml`:
```yaml
apiVersion: 1

providers:
  - name: 'Rideshare Dashboards'
    orgId: 1
    folder: 'Rideshare Simulation'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
      foldersFromFilesStructure: true
```

## References
- [Grafana Dashboard Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/#dashboards)
