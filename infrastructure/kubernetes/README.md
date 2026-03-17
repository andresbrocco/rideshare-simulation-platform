# infrastructure/kubernetes

> Kubernetes deployment infrastructure for the rideshare platform, covering a local Kind cluster (development) and AWS EKS (production) via Kustomize overlays, ArgoCD GitOps, and External Secrets Operator integration.

## Quick Reference

### Environment Variables

ConfigMaps and Secrets are the authoritative source. The table below lists keys consumed by workloads, grouped by their source object.

#### ConfigMap: `core-config`

| Key | Default (local) | Purpose |
|-----|-----------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka-0.kafka:29092` | Kafka broker address (headless DNS) |
| `KAFKA_SCHEMA_REGISTRY_URL` | `http://schema-registry:8081` | Schema Registry endpoint |
| `KAFKA_GROUP_ID` | `stream-processor` | Default consumer group |
| `REDIS_HOST` | `redis` | Redis service hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `OSRM_BASE_URL` | `http://osrm:5000` | OSRM routing service |
| `SIM_SPEED_MULTIPLIER` | `1` | Simulation speed factor |
| `SIM_CHECKPOINT_INTERVAL` | `300` | Seconds between SQLite checkpoints |
| `SIM_DB_PATH` | `/app/db/simulation.db` | SQLite DB path (emptyDir — lost on restart) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `otel-collector:4317` | OTLP gRPC exporter endpoint |
| `DEPLOYMENT_ENV` | `local` | Environment tag for telemetry |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Allowed CORS origins for the API |

#### ConfigMap: `data-pipeline-config`

| Key | Default (local) | Purpose |
|-----|-----------------|---------|
| `MINIO_ENDPOINT` | `minio:9000` | MinIO S3-compatible endpoint |
| `AIRFLOW_POSTGRES_HOST` | `airflow-postgres` | Airflow metadata DB host |
| `POSTGRES_METASTORE_HOST` | `postgres-metastore` | Hive Metastore DB host |
| `HIVE_METASTORE_URI` | `thrift://hive-metastore:9083` | Thrift URI for Trino catalog (duckdb overlay) |
| `TRINO_HOST` / `TRINO_PORT` | `trino` / `8080` | Trino query engine |
| `LOCALSTACK_ENDPOINT` | `http://localstack:4566` | LocalStack AWS emulator |
| `AWS_REGION` | `us-east-1` | AWS region for all SDK calls |

#### Secret: `app-credentials` (managed by ESO)

All values are injected by External Secrets Operator from LocalStack (dev) or AWS Secrets Manager (prod). Keys:

`REDIS_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `AIRFLOW_POSTGRES_PASSWORD`, `POSTGRES_METASTORE_USER`, `POSTGRES_METASTORE_PASSWORD`, `FERNET_KEY`, `AIRFLOW_ADMIN_USERNAME`, `AIRFLOW_ADMIN_PASSWORD`, `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`, `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`

#### Secret: `api-keys` (managed by ESO)

| Key | Purpose |
|-----|---------|
| `API_KEY` | Shared API key for simulation REST and WebSocket auth |

### Overlay-Specific Variables (production only)

| Variable | Used by | Source |
|----------|---------|--------|
| `DBT_RUNNER` | `airflow-scheduler`, `airflow-webserver` | Overlay patch (`duckdb` or `glue`) |
| `GLUE_ROLE_ARN` | `airflow-scheduler`, `airflow-webserver` | `production-glue` overlay patch (set from Terraform output) |
| `DEPLOYMENT_ENV` | `performance-controller` | `aws-production` component patch (`production`) |

### Cluster Service Ports (in-cluster)

| Service | Port | Protocol | Notes |
|---------|------|----------|-------|
| simulation | 8000 | HTTP | API + WebSocket; health at `/health` |
| stream-processor | 8080 | HTTP | Health at `/health` |
| kafka (headless) | 29092 | PLAINTEXT | StatefulSet DNS: `kafka-0.kafka:29092` |
| schema-registry | 8081 | HTTP | `/subjects` health check |
| redis | 6379 | TCP | |
| minio | 9000 | HTTP | S3 API; health at `/minio/health/live` |
| minio console | 9001 | HTTP | MinIO web UI |
| trino | 8080 | HTTP | Query UI |
| hive-metastore | 9083 | Thrift | Used only in `production-duckdb` overlay |
| airflow-webserver | 8082 | HTTP | Airflow UI |
| prometheus | 9090 | HTTP | |
| grafana | 3001 | HTTP | |
| osrm | 5000 | HTTP | Routing API |
| otel-collector | 4317 | gRPC | OTLP traces/metrics |
| localstack | 4566 | HTTP | AWS API emulator (local only) |

### Gateway Routes (local Kind — `localhost`)

| Path prefix | Backend service | Port |
|-------------|----------------|------|
| `/api/` | simulation | 8000 |
| `/airflow/` | airflow-webserver | 8082 |
| `/grafana/` | grafana | 3001 |
| `/prometheus/` | prometheus | 9090 |
| `/trino/` | trino | 8080 |
| `/` | control-panel (frontend) | 80 |

Host port mappings on the Kind control-plane node: `80` (HTTP), `443` (HTTPS), `30000–30001` (NodePort).

### Commands

#### Local Development (Kind)

```bash
# 1. Create Kind cluster and install External Secrets Operator
./infrastructure/kubernetes/scripts/create-cluster.sh

# 2. Deploy all services (imperative apply — dev path only)
./infrastructure/kubernetes/scripts/deploy-services.sh

# 3. Verify cluster health
./infrastructure/kubernetes/scripts/health-check.sh

# 4. Run connectivity smoke tests
./infrastructure/kubernetes/scripts/smoke-test.sh

# 5. Tear down cluster (add --preserve-data to back up PVC data first)
./infrastructure/kubernetes/scripts/teardown.sh
./infrastructure/kubernetes/scripts/teardown.sh --preserve-data --backup-dir=/tmp
```

#### kubectl Diagnostics

```bash
# Pod overview
kubectl get pods -o wide

# Watch pod status
kubectl get pods -w

# Logs for a service
kubectl logs -l app=simulation --tail=100 -f

# Decode a secret value
kubectl get secret api-keys -o jsonpath='{.data.API_KEY}' | base64 -d

# View a ConfigMap
kubectl get configmap core-config -o yaml

# Check External Secret sync status
kubectl get externalsecret -A
kubectl describe externalsecret app-credentials-sync

# Check PVC binding
kubectl get pvc

# Force pod restart
kubectl rollout restart deployment/simulation
```

#### Production (ArgoCD / EKS)

```bash
# Preview rendered manifests for an overlay before applying
kubectl kustomize infrastructure/kubernetes/overlays/production-duckdb | less
kubectl kustomize infrastructure/kubernetes/overlays/production-glue | less

# Install ArgoCD into the cluster
kubectl apply -f infrastructure/kubernetes/argocd/install.yaml

# Apply the ArgoCD Application (edit path first — see Configuration Files below)
kubectl apply -f infrastructure/kubernetes/argocd/app-rideshare-platform.yaml

# Manual sync via ArgoCD CLI
argocd app sync rideshare-platform

# Force ArgoCD to re-read Git (useful after pushing to deploy branch)
argocd app get rideshare-platform --refresh
```

#### Config and Secrets (local)

```bash
# Apply ConfigMaps and Secrets manually (already handled by deploy-services.sh)
kubectl apply -f infrastructure/kubernetes/manifests/configmap-core.yaml
kubectl apply -f infrastructure/kubernetes/manifests/configmap-data-pipeline.yaml
kubectl apply -f infrastructure/kubernetes/manifests/secret-credentials.yaml
kubectl apply -f infrastructure/kubernetes/manifests/secret-api-keys.yaml

# Validate config and secrets are correctly wired
./infrastructure/kubernetes/tests/test_config_secrets.sh
```

#### Test Suites

```bash
# Config/Secrets wiring
./infrastructure/kubernetes/tests/test_config_secrets.sh

# Core service connectivity (Kafka, Redis, MinIO)
./infrastructure/kubernetes/tests/test_core_services.sh

# ArgoCD sync status
./infrastructure/kubernetes/tests/test_argocd.sh

# Ingress routing
./infrastructure/kubernetes/tests/test_ingress.sh

# PVC persistence
./infrastructure/kubernetes/tests/test_persistence.sh

# Data platform (Trino, Hive Metastore, MinIO)
./infrastructure/kubernetes/tests/test_data_platform.sh

# Pod/deployment lifecycle
./infrastructure/kubernetes/tests/test_lifecycle.sh
```

### Configuration Files

| File | Purpose |
|------|---------|
| `kind/cluster-config.yaml` | Kind cluster spec (1 control-plane + 2 workers; port mappings 80/443/30000-30001) |
| `manifests/configmap-core.yaml` | Core service configuration (Kafka, Redis, OSRM, OTel, API) |
| `manifests/configmap-data-pipeline.yaml` | Data pipeline configuration (MinIO, PostgreSQL, Hive, Trino, LocalStack) |
| `manifests/secret-credentials.yaml` | Reference-only Secret (real values injected by ESO) |
| `manifests/secret-api-keys.yaml` | Reference-only API key Secret (real values injected by ESO) |
| `manifests/external-secrets-secretstore.yaml` | ESO `SecretStore` pointing at LocalStack (dev) or AWS Secrets Manager (prod via env var) |
| `argocd/app-rideshare-platform.yaml` | ArgoCD Application spec — **edit `path:` before applying** to choose overlay |
| `overlays/production-duckdb/kustomization.yaml` | Production overlay with Hive Metastore + RDS; `DBT_RUNNER=duckdb` |
| `overlays/production-glue/kustomization.yaml` | Production overlay using AWS Glue catalog; `DBT_RUNNER=glue` |
| `components/aws-production/kustomization.yaml` | Shared EKS patches: EBS StorageClass, IRSA service accounts, ALB ingress, ECR images |

### Persistent Volumes (local Kind)

| PVC | Service | Size | Data |
|-----|---------|------|------|
| `minio-data` | MinIO | 10 Gi | Bronze/Silver/Gold Delta Lake tables |
| `airflow-postgres-data` | Airflow PostgreSQL | 5 Gi | DAG run history, task metadata |
| `postgres-metastore-data` | Hive Metastore PostgreSQL | 5 Gi | Table schema definitions |
| `kafka-data` | Kafka | 5 Gi | Topic message logs |

StorageClass reclaim policy is `Delete` — PVC deletion immediately destroys the underlying PV. Always back up before deleting PVCs.

## Common Tasks

### Switch Between DuckDB and Glue Overlays

Edit `argocd/app-rideshare-platform.yaml`, changing the `spec.source.path` field:

```yaml
# For DBT_RUNNER=duckdb (Hive Metastore + RDS):
path: infrastructure/kubernetes/overlays/production-duckdb

# For DBT_RUNNER=glue (AWS Glue Data Catalog, no Hive Metastore):
path: infrastructure/kubernetes/overlays/production-glue
```

For the Glue overlay, also replace `<glue-role-arn>` in the overlay's inline patch with the value from:

```bash
terraform -chdir=infrastructure/terraform/foundation output -raw glue_job_role_arn
```

Then push to the `deploy` branch. ArgoCD self-heals within 3 minutes.

### Bootstrap a Local Kind Cluster from Scratch

```bash
# Prerequisites: kind, kubectl, helm
./infrastructure/kubernetes/scripts/create-cluster.sh
./infrastructure/kubernetes/scripts/deploy-services.sh
./infrastructure/kubernetes/scripts/health-check.sh
./infrastructure/kubernetes/scripts/smoke-test.sh
```

### Back Up Stateful Data Before Cluster Deletion

```bash
# MinIO (Delta Lake tables)
MINIO_POD=$(kubectl get pod -l app=minio -o jsonpath='{.items[0].metadata.name}')
kubectl exec $MINIO_POD -- tar czf /tmp/minio-backup.tar.gz -C /data .
kubectl cp $MINIO_POD:/tmp/minio-backup.tar.gz ./minio-backup-$(date +%Y%m%d-%H%M%S).tar.gz

# Airflow PostgreSQL
POSTGRES_POD=$(kubectl get pod -l app=airflow-postgres -o jsonpath='{.items[0].metadata.name}')
kubectl exec $POSTGRES_POD -- pg_dump -U airflow -d airflow -Fc > airflow-backup-$(date +%Y%m%d-%H%M%S).dump

# Or use the teardown script with built-in backup
./infrastructure/kubernetes/scripts/teardown.sh --preserve-data --backup-dir=/tmp
```

See `manifests/BACKUP_RESTORE.md` for full restore procedures.

### Check Why a Pod Is Not Starting

```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name> --previous   # logs from last crash
kubectl get events --sort-by=.metadata.creationTimestamp
```

### Rotate Secrets

Secrets are managed via External Secrets Operator. To rotate:

1. Update the secret value in LocalStack (dev) or AWS Secrets Manager (prod).
2. Force ESO to re-sync: `kubectl annotate externalsecret <name> force-sync=$(date +%s) --overwrite`
3. Restart the affected pod: `kubectl rollout restart deployment/<name>`

### Register Bronze Delta Tables (production)

The `bronze-init` CronJob runs every 10 minutes automatically. To trigger manually:

```bash
kubectl create job --from=cronjob/bronze-init bronze-init-manual-$(date +%s)
kubectl logs -l job-name=bronze-init-manual-... -f
```

## Troubleshooting

**ESO secrets not syncing**
- Check `kubectl get externalsecret -A` for `SecondsSinceLastSync` and error conditions.
- In local Kind, verify LocalStack pod is running: `kubectl get pod -l app=localstack`.
- ESO controller env var `AWS_ENDPOINT_URL` must point at `http://localstack.default.svc.cluster.local:4566` (set during helm install).

**Simulation pod crash-loops**
- Simulation has 5 init containers that wait for Kafka, Schema Registry, Redis, OSRM, and Stream Processor in sequence. A crash-loop usually means one of these dependencies is not healthy. Check: `kubectl describe pod -l app=simulation`.

**ArgoCD reverts manual kubectl changes**
- `selfHeal: true` is set on the ArgoCD Application. Out-of-band changes (except replica counts, which are in `ignoreDifferences`) are reverted within ~3 minutes. To make permanent changes, commit to the `deploy` branch.

**StorageClass "field is immutable" error**
- Benign. Kind ships a default `standard` StorageClass that conflicts on re-apply. The `deploy-services.sh` script suppresses this error intentionally.

**PVC stuck in Pending**
- In local Kind, static PVs in `pv-static.yaml` are bound to node names `rideshare-local-worker` and `rideshare-local-worker2`. Verify your cluster was created with `create-cluster.sh` using the correct `kind-config.yaml`.

**Simulation SQLite checkpoint lost after pod restart**
- `simulation.db` is mounted from an `emptyDir` — it does not persist across pod restarts. This is by design for local dev. There is no persistent volume for this database in any manifest.

**ArgoCD Application path contains literal placeholder**
- The file `argocd/app-rideshare-platform.yaml` ships with `overlays/production-<dbt-runner>` as the path. Replace `<dbt-runner>` with `duckdb` or `glue` before applying.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context: overlay patterns, ESO wiring, ArgoCD deploy branch behavior
- [infrastructure/docker/README.md](../docker/README.md) — Local Docker Compose alternative (development)
- [infrastructure/scripts/README.md](../scripts/README.md) — CI/CD and operational scripts
- [infrastructure/terraform/CONTEXT.md](../terraform/CONTEXT.md) — EKS cluster, RDS, S3, IAM provisioning
- [manifests/BACKUP_RESTORE.md](manifests/BACKUP_RESTORE.md) — Full backup and restore procedures
- [manifests/README-CONFIG.md](manifests/README-CONFIG.md) — ConfigMap and Secret reference guide
