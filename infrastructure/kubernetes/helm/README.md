# Helm Chart Considerations

## Overview

This directory is reserved for Helm charts that could be used to package and deploy the rideshare simulation platform in production environments. The current implementation uses plain Kubernetes manifests (located in `../manifests/`) for simplicity and learning purposes.

## Why Helm?

For production deployments, Helm provides several advantages over plain manifests:

1. **Templating**: Parameterize configurations for different environments (dev, staging, prod)
2. **Package Management**: Bundle related resources together as a single deployable unit
3. **Version Control**: Track releases and enable easy rollbacks
4. **Dependency Management**: Manage dependencies between charts
5. **Values Override**: Easily customize deployments without modifying templates

## Migration Path

To convert the current manifests to a Helm chart:

### 1. Chart Structure
```
helm/
├── rideshare-platform/
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-dev.yaml
│   ├── values-prod.yaml
│   └── templates/
│       ├── core/
│       │   ├── kafka.yaml
│       │   ├── redis.yaml
│       │   ├── osrm.yaml
│       │   ├── simulation.yaml
│       │   └── stream-processor.yaml
│       ├── data-platform/
│       │   ├── minio.yaml
│       │   ├── spark-master.yaml
│       │   ├── spark-worker.yaml
│       │   ├── spark-thrift-server.yaml
│       │   └── localstack.yaml
│       ├── orchestration/
│       │   ├── airflow-postgres.yaml
│       │   ├── airflow-webserver.yaml
│       │   └── airflow-scheduler.yaml
│       ├── analytics/
│       │   ├── superset-postgres.yaml
│       │   ├── superset-redis.yaml
│       │   └── superset.yaml
│       └── monitoring/
│           ├── prometheus.yaml
│           └── grafana.yaml
```

### 2. Values File Example
```yaml
# values.yaml
global:
  namespace: rideshare
  environment: dev

resources:
  kafka:
    memory: 1Gi
  simulation:
    memory: 1Gi
  spark:
    master:
      memory: 512Mi
    worker:
      memory: 2Gi

replicaCounts:
  simulation: 1
  sparkWorker: 1

persistence:
  enabled: false  # Use emptyDir for dev
  storageClass: standard
```

### 3. Template Example
```yaml
# templates/data-platform/spark-master.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {{ include "rideshare.fullname" . }}-spark-master
  labels:
    {{- include "rideshare.labels" . | nindent 4 }}
    app: spark-master
spec:
  serviceName: spark-master
  replicas: {{ .Values.replicaCounts.sparkMaster | default 1 }}
  selector:
    matchLabels:
      app: spark-master
  template:
    metadata:
      labels:
        app: spark-master
    spec:
      containers:
      - name: spark-master
        image: {{ .Values.images.spark.repository }}:{{ .Values.images.spark.tag }}
        resources:
          limits:
            memory: {{ .Values.resources.spark.master.memory }}
```

### 4. Installation Commands
```bash
# Install chart
helm install rideshare ./helm/rideshare-platform -f ./helm/rideshare-platform/values-dev.yaml

# Upgrade chart
helm upgrade rideshare ./helm/rideshare-platform -f ./helm/rideshare-platform/values-dev.yaml

# Rollback
helm rollback rideshare 1

# Uninstall
helm uninstall rideshare
```

## Existing Helm Charts

Consider using official Helm charts for complex services:

- **Apache Airflow**: https://airflow.apache.org/docs/helm-chart/
- **Apache Superset**: https://github.com/apache/superset/tree/master/helm/superset
- **Prometheus**: https://github.com/prometheus-community/helm-charts
- **Grafana**: https://github.com/grafana/helm-charts
- **MinIO**: https://github.com/minio/minio/tree/master/helm/minio

These charts provide production-ready configurations with:
- High availability setups
- Security best practices
- Resource tuning
- Backup and restore capabilities

## Current Status

**Status**: Not Implemented

The project currently uses plain Kubernetes manifests for:
- Simplicity and transparency
- Learning and portfolio demonstration
- Easier debugging and customization
- No external dependencies

## Future Work

When migrating to production or scaling the platform:

1. Create Helm chart structure
2. Extract common values to `values.yaml`
3. Add environment-specific values files
4. Implement proper secret management (sealed secrets, external secrets operator)
5. Add PersistentVolumeClaims for stateful services
6. Configure resource quotas and limits
7. Add network policies
8. Implement RBAC policies
9. Add liveness and readiness probes tuning
10. Configure autoscaling (HPA for applicable services)

## References

- **Helm Documentation**: https://helm.sh/docs/
- **Helm Best Practices**: https://helm.sh/docs/chart_best_practices/
- **Kubernetes Patterns**: https://www.redhat.com/en/resources/oreilly-kubernetes-patterns-ebook
