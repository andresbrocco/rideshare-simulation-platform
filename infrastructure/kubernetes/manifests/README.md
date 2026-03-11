# Kubernetes Manifests

> Base Kubernetes resource definitions for all platform services, designed to be patched by Kustomize overlays for environment-specific configuration.

## Quick Reference

### Service Ports (ClusterIP)

| Service | Port | Protocol |
|---------|------|----------|
| simulation | 8000 | HTTP |
| stream-processor | 8080 | HTTP |
| bronze-ingestion | 8080 | HTTP |
| kafka | 29092 (internal), 9092 (external), 29093 (controller) | TCP |
| schema-registry | 8081 | HTTP |
| redis | 6379 | TCP |
| osrm | 5000 | HTTP |
| airflow-webserver | 8082 (service) → 8080 (container) | HTTP |
| trino | 8080 | HTTP |
| grafana | 3001 | HTTP |
| prometheus | 9090 | HTTP |
| minio | 9000 (API), 9001 (console) | HTTP |
| hive-metastore | 9083 | Thrift |
| airflow-postgres | 5432 | PostgreSQL |
| postgres-metastore | 5432 | PostgreSQL |
| otel-collector | 4317 | gRPC (OTLP) |

### Gateway Routes

All external access flows through Envoy Gateway (`rideshare-gateway`, port 80). Path prefix is stripped before forwarding.

| External Path | Backend Service | Backend Port |
|---------------|----------------|--------------|
| `/api/` | simulation | 8000 |
| `/` (root) | frontend (control-panel) | 80 |
| `/airflow/` | airflow-webserver | 8082 |
| `/grafana/` | grafana | 3001 |
| `/prometheus/` | prometheus | 9090 |
| `/trino/` | trino | 8080 |

### Health Endpoints

| Service | Health Path | Port | Notes |
|---------|------------|------|-------|
| simulation | `/health` | 8000 | initialDelaySeconds: 90 |
| stream-processor | `/health` | 8080 | initialDelaySeconds: 10 |
| bronze-ingestion | `/health` | 8080 | initialDelaySeconds: 10 |
| airflow-webserver | `/api/v2/monitor/health` | 8080 | initialDelaySeconds: 600 |
| osrm | `/route/v1/driving/-46.6333,-23.5505;-46.6334,-23.5506` | 5000 | initialDelaySeconds: 180–300 (road network load time) |

### ConfigMaps

#### `core-config` — Core Services

| Key | Default Value | Description |
|-----|---------------|-------------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka-0.kafka:29092` | Kafka internal broker address |
| `KAFKA_SECURITY_PROTOCOL` | `PLAINTEXT` | Kafka wire protocol |
| `KAFKA_SCHEMA_REGISTRY_URL` | `http://schema-registry:8081` | Schema Registry URL |
| `KAFKA_AUTO_OFFSET_RESET` | `latest` | Consumer offset policy |
| `KAFKA_GROUP_ID` | `stream-processor` | Default consumer group |
| `REDIS_HOST` | `redis` | Redis service DNS |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_SSL` | `false` | Redis TLS toggle |
| `OSRM_BASE_URL` | `http://osrm:5000` | OSRM routing service |
| `SIM_SPEED_MULTIPLIER` | `1` | Simulation time scaling |
| `SIM_LOG_LEVEL` | `INFO` | Simulation log verbosity |
| `SIM_CHECKPOINT_INTERVAL` | `300` | Checkpoint frequency in seconds |
| `SIM_DB_PATH` | `/app/db/simulation.db` | SQLite checkpoint path |
| `PROCESSOR_WINDOW_SIZE_MS` | `100` | Stream aggregation window |
| `PROCESSOR_AGGREGATION_STRATEGY` | `latest` | Aggregation mode |
| `PROCESSOR_TOPICS` | `gps_pings,trips,driver_status,surge_updates` | Kafka topics consumed |
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8080` | API bind port |
| `LOG_LEVEL` | `INFO` | Application log level |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Allowed CORS origins |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `otel-collector:4317` | OTel collector gRPC |
| `DEPLOYMENT_ENV` | `local` | Environment label |
| `LOG_FORMAT` | `json` | Log output format |

#### `data-pipeline-config` — Data Pipeline Services

| Key | Default Value | Description |
|-----|---------------|-------------|
| `MINIO_ENDPOINT` | `minio:9000` | MinIO S3-compatible endpoint |
| `MINIO_CONSOLE_PORT` | `9001` | MinIO web console port |
| `MINIO_USE_SSL` | `false` | MinIO TLS toggle |
| `AIRFLOW_POSTGRES_HOST` | `airflow-postgres` | Airflow metadata DB host |
| `AIRFLOW_POSTGRES_PORT` | `5432` | Airflow metadata DB port |
| `AIRFLOW_POSTGRES_DB` | `airflow` | Airflow metadata DB name |
| `AIRFLOW_POSTGRES_USER` | `airflow` | Airflow DB user |
| `POSTGRES_METASTORE_HOST` | `postgres-metastore` | Hive metastore DB host |
| `POSTGRES_METASTORE_PORT` | `5432` | Hive metastore DB port |
| `POSTGRES_METASTORE_DB` | `metastore` | Hive metastore DB name |
| `POSTGRES_METASTORE_USER` | `hive` | Hive metastore DB user |
| `HIVE_METASTORE_URI` | `thrift://hive-metastore:9083` | Thrift URI for Trino/Spark |
| `TRINO_HOST` | `trino` | Trino coordinator DNS |
| `TRINO_PORT` | `8080` | Trino HTTP port |
| `LOCALSTACK_ENDPOINT` | `http://localstack:4566` | LocalStack AWS emulator |
| `AWS_REGION` | `us-east-1` | AWS region |

### Secrets

Secrets are managed by External Secrets Operator (ESO), synced from LocalStack Secrets Manager (dev) or AWS Secrets Manager (prod). The `secret-*.yaml` files are reference documentation only — do not apply them directly in production.

#### Secret: `app-credentials`

| Key | Source Secret | Source Property |
|-----|--------------|-----------------|
| `REDIS_PASSWORD` | `rideshare/core` | `REDIS_PASSWORD` |
| `MINIO_ROOT_USER` | `rideshare/data-pipeline` | `MINIO_ROOT_USER` |
| `MINIO_ROOT_PASSWORD` | `rideshare/data-pipeline` | `MINIO_ROOT_PASSWORD` |
| `MINIO_ACCESS_KEY` | `rideshare/data-pipeline` | `MINIO_ROOT_USER` |
| `MINIO_SECRET_KEY` | `rideshare/data-pipeline` | `MINIO_ROOT_PASSWORD` |
| `AIRFLOW_POSTGRES_PASSWORD` | `rideshare/data-pipeline` | `POSTGRES_AIRFLOW_PASSWORD` |
| `POSTGRES_METASTORE_PASSWORD` | `rideshare/data-pipeline` | `POSTGRES_METASTORE_PASSWORD` |
| `POSTGRES_METASTORE_USER` | `rideshare/data-pipeline` | `POSTGRES_METASTORE_USER` |
| `FERNET_KEY` | `rideshare/data-pipeline` | `FERNET_KEY` |
| `AIRFLOW_ADMIN_PASSWORD` | `rideshare/data-pipeline` | `ADMIN_PASSWORD` |
| `AIRFLOW_JWT_SECRET` | `rideshare/data-pipeline` | `JWT_SECRET` |
| `GRAFANA_ADMIN_USER` | `rideshare/monitoring` | `ADMIN_USER` |
| `GRAFANA_ADMIN_PASSWORD` | `rideshare/monitoring` | `ADMIN_PASSWORD` |
| `KAFKA_SASL_USERNAME` | `rideshare/core` | `KAFKA_SASL_USERNAME` |
| `KAFKA_SASL_PASSWORD` | `rideshare/core` | `KAFKA_SASL_PASSWORD` |
| `KAFKA_SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO` | `rideshare/core` | `SCHEMA_REGISTRY_BASIC_AUTH_USER_INFO` |
| `TRINO_ADMIN_PASSWORD_HASH` | `rideshare/trino-admin-password-hash` | `hash` |
| `TRINO_VISITOR_PASSWORD_HASH` | `rideshare/trino-visitor-password-hash` | `hash` |

#### Secret: `api-keys`

| Key | Source Secret | Source Property |
|-----|--------------|-----------------|
| `API_KEY` | `rideshare/api-key` | `API_KEY` |

### Kafka Topics (created by `kafka-init` Job)

| Topic | Partitions | Description |
|-------|------------|-------------|
| `_schemas` | 1 | Schema Registry internal (compact) |
| `gps_pings` | 8 | Real-time driver GPS coordinates |
| `trips` | 4 | Trip lifecycle events |
| `driver_status` | 2 | Driver state transitions |
| `surge_updates` | 2 | Surge pricing zone updates |
| `ratings` | 2 | Trip ratings |
| `payments` | 2 | Payment events |
| `driver_profiles` | 1 | Driver onboarding |
| `rider_profiles` | 1 | Rider onboarding |

### Persistent Storage

| PVC | Service | Size | Data |
|-----|---------|------|------|
| `minio-data` | MinIO | 10Gi | Delta Lake tables (Bronze/Silver/Gold) |
| `airflow-postgres-data` | Airflow PostgreSQL | 5Gi | DAG runs, task history |
| `postgres-metastore-data` | Hive Metastore PostgreSQL | 5Gi | Table metadata, schema definitions |
| `kafka-data` | Kafka | 5Gi | Message logs |

StorageClass: `rancher.io/local-path` provisioner (`standard`), reclaim policy `Delete`. Volumes are permanently lost when PVCs are deleted.

### Key Files

| File | Kind | Description |
|------|------|-------------|
| `configmap-core.yaml` | ConfigMap | Shared env vars for core services |
| `configmap-data-pipeline.yaml` | ConfigMap | Env vars for data pipeline services |
| `secret-credentials.yaml` | Secret (reference only) | Placeholder — ESO manages actual values |
| `secret-api-keys.yaml` | Secret (reference only) | Placeholder — ESO manages actual values |
| `external-secrets-secretstore.yaml` | SecretStore | Points to AWS/LocalStack Secrets Manager |
| `external-secrets-app-credentials.yaml` | ExternalSecret | Syncs `app-credentials` from Secrets Manager |
| `external-secrets-api-keys.yaml` | ExternalSecret | Syncs `api-keys` from Secrets Manager |
| `gateway.yaml` | Gateway | Envoy Gateway on port 80 |
| `httproute-api.yaml` | HTTPRoute | Routes `/api/` to simulation, `/` to frontend |
| `httproute-web-services.yaml` | HTTPRoute | Routes Airflow, Grafana, Prometheus, Trino UIs |
| `pv-static.yaml` | PersistentVolume | hostPath PVs with node affinity (local only) |
| `storageclass.yaml` | StorageClass | `rancher.io/local-path` provisioner |
| `trino.yaml` (ConfigMap `trino-config`) | ConfigMap | Includes `password-authenticator.properties`, `access-control.properties`, `rules.json`, `event-listener.properties`, and `password.db.template` for FILE-based auth and visitor access control |
| `grafana.yaml` (ConfigMap `grafana-dashboards-admin`) | ConfigMap | Admin folder dashboard: `visitor-activity.json` — aggregates Airflow login history and Loki audit events |

## Commands

### Apply Manifests

```bash
# Apply everything at once (local dev)
kubectl apply -f infrastructure/kubernetes/manifests/

# Apply ConfigMaps and Secrets only
kubectl apply -f infrastructure/kubernetes/manifests/configmap-core.yaml
kubectl apply -f infrastructure/kubernetes/manifests/configmap-data-pipeline.yaml
kubectl apply -f infrastructure/kubernetes/manifests/secret-credentials.yaml
kubectl apply -f infrastructure/kubernetes/manifests/secret-api-keys.yaml

# Apply via Kustomize overlay (production)
kubectl apply -k infrastructure/kubernetes/overlays/production-duckdb/
kubectl apply -k infrastructure/kubernetes/overlays/production-glue/
```

### Inspect Configuration

```bash
# View ConfigMap values
kubectl get configmap core-config -o yaml
kubectl get configmap data-pipeline-config -o yaml

# View Secret keys (values are base64-encoded)
kubectl get secret app-credentials -o yaml

# Decode a specific secret value
kubectl get secret api-keys -o jsonpath='{.data.API_KEY}' | base64 -d

# Check External Secrets sync status
kubectl get externalsecret
kubectl describe externalsecret app-credentials-sync
```

### Service Health

```bash
# Check all pod status
kubectl get pods

# Check a specific service health endpoint (port-forward required)
kubectl port-forward svc/simulation 8000:8000
curl http://localhost:8000/health

kubectl port-forward svc/stream-processor 8080:8080
curl http://localhost:8080/health

# Check Airflow health
kubectl port-forward svc/airflow-webserver 8082:8082
curl http://localhost:8082/api/v2/monitor/health
```

### Kafka Operations

```bash
# Exec into Kafka pod
KAFKA_POD=$(kubectl get pod -l app=kafka -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it $KAFKA_POD -- bash

# List topics from outside the cluster (port-forward)
kubectl port-forward svc/kafka 9092:9092
# (use kafka-topics --bootstrap-server localhost:9092 --list)

# Check kafka-init Job logs
kubectl logs job/kafka-init
```

### Validate Config and Secrets

```bash
./infrastructure/kubernetes/tests/test_config_secrets.sh
```

## Common Tasks

### Adding a New ConfigMap Key

1. Add the key to the appropriate ConfigMap YAML (`configmap-core.yaml` or `configmap-data-pipeline.yaml`).
2. Reference it in the service manifest using `configMapKeyRef` or `envFrom`.
3. Apply: `kubectl apply -f infrastructure/kubernetes/manifests/configmap-core.yaml`.

### Adding a New Secret

1. Add the secret path and property to the appropriate ExternalSecret YAML (`external-secrets-app-credentials.yaml` or `external-secrets-api-keys.yaml`).
2. Store the secret value in LocalStack Secrets Manager: `aws secretsmanager put-secret-value --secret-id rideshare/core --secret-string '{"NEW_KEY":"value"}' --profile rideshare`.
3. Force ESO re-sync: `kubectl annotate externalsecret app-credentials-sync force-sync=$(date +%s) --overwrite`.

### Switching to AWS Secrets Manager (Production)

The `SecretStore` and `ExternalSecret` CRDs are identical for local and production. Only the ESO controller endpoint changes:

1. Remove `--set env[0].*` flags referencing LocalStack from the ESO Helm install command.
2. Replace the `aws-credentials` Secret in the `external-secrets` namespace with IAM role-based auth (EKS Pod Identity).
3. No changes needed to manifests in this directory.

### Rebuilding a Pod to Pick Up Config Changes

```bash
kubectl rollout restart deployment/simulation
kubectl rollout restart deployment/stream-processor
```

### Scaling a Service

Replicas are patched by Kustomize overlays. For a local one-off change:

```bash
kubectl scale deployment simulation --replicas=2
```

## Troubleshooting

### Simulation Pod Stuck in Init

The simulation Deployment has five sequential initContainers (Kafka, Schema Registry, Redis, OSRM, Stream Processor). If stuck:

```bash
kubectl describe pod -l app=simulation
# Look for which initContainer is waiting
kubectl logs -l app=simulation -c wait-for-kafka
kubectl logs -l app=simulation -c wait-for-osrm
```

OSRM has the longest startup time (180–300s) because it must load the pre-processed Sao Paulo road network on first boot.

### Secrets Not Populating (ESO Sync Failure)

```bash
kubectl get externalsecret
# STATUS should be "SecretSynced"

kubectl describe externalsecret app-credentials-sync
# Check Events section for error messages

# Verify LocalStack is running and the secret path exists
kubectl port-forward svc/localstack 4566:4566
aws --endpoint-url http://localhost:4566 secretsmanager list-secrets --profile rideshare
```

If the ESO SecretStore itself is not ready, check the ESO controller is installed in the `external-secrets` namespace and that the `aws-credentials` Secret exists there.

### ConfigMap Values Not Reflected in Running Pod

Pods do not automatically reload when ConfigMaps change. After applying ConfigMap updates:

```bash
kubectl rollout restart deployment/<service-name>
```

### PVC Data Loss Warning

The StorageClass uses reclaim policy `Delete`. If a PVC is deleted the underlying PV and all data are immediately and permanently gone. Before deleting any PVC, run a backup:

```bash
MINIO_POD=$(kubectl get pod -l app=minio -o jsonpath='{.items[0].metadata.name}')
kubectl exec $MINIO_POD -- tar czf /tmp/minio-backup.tar.gz -C /data .
kubectl cp $MINIO_POD:/tmp/minio-backup.tar.gz ./minio-backup-$(date +%Y%m%d-%H%M%S).tar.gz
kubectl exec $MINIO_POD -- rm /tmp/minio-backup.tar.gz
```

See `BACKUP_RESTORE.md` for full backup and restore procedures for all stateful services.

### Gateway Routes Not Working

```bash
kubectl get gateway
kubectl get httproute
kubectl describe httproute api-route
kubectl describe httproute web-services-route
```

Ensure the Envoy Gateway GatewayClass (`eg`) is installed and the gateway has an assigned address.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context: Gateway API, External Secrets, static PV patterns, initContainer startup ordering
- [BACKUP_RESTORE.md](BACKUP_RESTORE.md) — Backup and restore procedures for all stateful PVCs
- [README-CONFIG.md](README-CONFIG.md) — ConfigMap and Secret usage patterns (envFrom vs individual key references)
- [infrastructure/kubernetes/overlays](../overlays/CONTEXT.md) — Kustomize overlays that patch these base manifests for production
- [infrastructure/kubernetes/scripts](../scripts/CONTEXT.md) — Scripts for cluster creation, deployment, and health checks
- [infrastructure/kubernetes/argocd](../argocd/CONTEXT.md) — GitOps configuration for production deployment
