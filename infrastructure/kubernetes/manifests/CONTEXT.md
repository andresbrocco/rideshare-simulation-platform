# CONTEXT.md — Kubernetes Manifests

## Purpose

Kubernetes resource definitions for deploying the rideshare simulation platform to a local Kind cluster. Contains declarative YAML manifests for all services, infrastructure components, networking, storage, and configuration management.

## Responsibility Boundaries

- **Owns**: Kubernetes resource definitions (Deployments, StatefulSets, DaemonSets, Jobs, Services, PVCs, ConfigMaps, Secrets, Gateway/HTTPRoutes)
- **Delegates to**: Lifecycle scripts (`infrastructure/kubernetes/scripts/`) for cluster creation, deployment orchestration, and teardown
- **Does not handle**: Cluster provisioning (handled by Kind cluster config), runtime configuration changes (use `kubectl apply`), or cloud provider resources (handled by Terraform)

## Key Concepts

**Service Categories**: Manifests are organized by service name, not by resource type. Each service typically includes multiple resources (Deployment/StatefulSet + Service + optional ConfigMap/PVC).

**Service Inventory**:
- **Core**: kafka, schema-registry, redis, osrm, simulation, stream-processor, frontend
- **Data Pipeline**: minio, minio-init (Job), postgres-metastore, hive-metastore, trino, bronze-ingestion, bronze-init (Job), airflow-postgres, airflow-webserver, airflow-scheduler, localstack
- **Spark Testing** (optional): spark-thrift-server (for dual-engine DBT validation)
- **Monitoring**: prometheus, loki, tempo, otel-collector, cadvisor (DaemonSet), grafana

**Gateway API**: Uses Kubernetes Gateway API (not Ingress) for HTTP routing. The `gateway.yaml` defines the entry point, while `httproute-*.yaml` files define path-based routing rules with URL rewriting.

**StatefulSet vs Deployment**: Kafka and postgres-metastore use StatefulSet for stable network identity and persistent storage. Most other services use Deployments. cAdvisor uses a DaemonSet. minio-init and bronze-init use Jobs.

**Configuration Strategy**: Two-tier configuration with ConfigMaps for non-sensitive values (`configmap-core.yaml`, `configmap-data-pipeline.yaml`) and Secrets for credentials (`secret-credentials.yaml`, `secret-api-keys.yaml`). Services load configuration via `envFrom` or individual `valueFrom` references.

**Observability Stack**: OpenTelemetry Collector receives metrics and traces via OTLP from simulation and stream-processor, forwards metrics to Prometheus (remote write) and traces to Tempo. Loki handles log aggregation. Grafana provides unified dashboards with Prometheus, Loki, Tempo, and Trino datasources. In K8s, the OTel Collector runs as a Deployment (not DaemonSet) and does not collect container logs directly; metrics and traces are pushed via OTLP.

**Storage Model**: Uses Kind's local-path-provisioner with `Delete` reclaim policy. PVCs are pre-created for stateful services (MinIO, PostgreSQL instances, Kafka). Critical data must be backed up before PVC deletion as volumes are automatically destroyed.

**Init Containers**: Services with dependencies use init containers to wait for upstream services (e.g., simulation waits for Kafka, Redis, OSRM, Schema Registry, Stream Processor). This ensures correct startup ordering without external orchestration.

## Non-Obvious Details

**Image Pull Policy**: Uses `imagePullPolicy: Never` for custom images (simulation, stream-processor, frontend, minio, bronze-ingestion, hive-metastore) as these are built locally and loaded into Kind with `kind load docker-image`.

**Kafka Listener Configuration**: Kafka exposes three ports: 9092 (external), 29092 (internal cluster communication), 29093 (KRaft controller). Internal services connect via `kafka-0.kafka.default.svc.cluster.local:29092`.

**Headless Service Pattern**: Kafka uses a headless service (`clusterIP: None`) to enable direct pod-to-pod communication and stable DNS names for StatefulSet pods.

**Gateway HTTPRoute Ordering**: HTTPRoute rules are evaluated in order. The frontend route (`/`) must be defined last as it matches all paths. More specific routes (e.g., `/api/`) must come first.

**Trino Config Init Container**: Trino requires config files at specific paths (`/etc/trino/`, `/etc/trino/catalog/`). An init container copies ConfigMap data into the correct directory structure since ConfigMap mounts are flat.

**OTel Collector K8s Adaptation**: The Docker Compose OTel Collector uses a `filelog` receiver to read Docker container logs from `/var/lib/docker/containers/`. In K8s, this is dropped; only OTLP-push metrics and traces are handled. Container log collection via DaemonSet would be a future enhancement.

**Existing Documentation**: `README-CONFIG.md` explains ConfigMap/Secret usage patterns. `BACKUP_RESTORE.md` provides operational procedures for stateful data. Both should be verified against actual manifests as they may become outdated.
