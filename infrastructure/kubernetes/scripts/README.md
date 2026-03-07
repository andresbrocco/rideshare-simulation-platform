# Kubernetes Scripts

> Lifecycle management scripts for the local Kind-based Kubernetes cluster — create, deploy, verify, and teardown the full platform stack.

## Quick Reference

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CLUSTER_NAME` | `rideshare-local` | Name of the Kind cluster to create/manage/delete |
| `BACKUP_DIR` | `/tmp` | Destination directory for `--preserve-data` backup tarballs |

### Commands

All scripts are run from the repository root:

```bash
# 1. Create cluster and install External Secrets Operator
./infrastructure/kubernetes/scripts/create-cluster.sh

# 2. Deploy all platform services in correct order
./infrastructure/kubernetes/scripts/deploy-services.sh

# 3. Verify Kubernetes-level health (nodes, pods, PVCs)
./infrastructure/kubernetes/scripts/health-check.sh

# 4. Run in-cluster functional smoke tests
./infrastructure/kubernetes/scripts/smoke-test.sh

# 5. Tear down the cluster (destroys all data)
./infrastructure/kubernetes/scripts/teardown.sh

# 5b. Tear down with data preserved to /tmp (timestamped tarball)
./infrastructure/kubernetes/scripts/teardown.sh --preserve-data

# 5c. Tear down with data preserved to a custom directory
./infrastructure/kubernetes/scripts/teardown.sh --preserve-data --backup-dir=/path/to/backup
```

### Script Overview

| Script | What it does |
|---|---|
| `create-cluster.sh` | Creates the Kind cluster using `infrastructure/kubernetes/kind/cluster-config.yaml`; installs ESO v0.11.0 via Helm; idempotent (exits 0 if cluster exists) |
| `deploy-services.sh` | Applies all manifests in a strict 6-step order (see below); waits for Kafka, Redis, and MinIO pods to reach Ready state |
| `health-check.sh` | Checks cluster connectivity, node readiness, pod counts by status (Running/Pending/Error), critical service pods (kafka, redis, minio), and PVC binding |
| `smoke-test.sh` | Runs 5 in-cluster functional probes via `kubectl exec`: Kafka broker API, Redis PING, MinIO health endpoint, DNS resolution, and storage write |
| `teardown.sh` | Deletes the Kind cluster; optionally backs up MinIO, Kafka, and Airflow Postgres data via `kubectl exec tar` before deletion |

### Prerequisites

| Tool | Required by |
|---|---|
| `kind` | `create-cluster.sh`, `teardown.sh` |
| `kubectl` | All scripts |
| `helm` | `create-cluster.sh` (ESO installation; skipped with warning if absent) |

### Deployment Order (deploy-services.sh)

The `deploy-services.sh` script applies manifests in this fixed sequence to satisfy service dependencies:

| Step | Resources |
|---|---|
| 0 | Gateway API CRDs (from external URL) |
| 1 | StorageClass, PersistentVolumes, PersistentVolumeClaims |
| 2 | ConfigMaps, Secrets, ExternalSecrets store and credentials |
| 3 | Data platform: MinIO, Hive Metastore, Trino, Bronze Ingestion, Airflow, LocalStack |
| 3b | ExternalSecret CRDs (applied after LocalStack is live so ESO can sync) |
| 4 | Core simulation: Kafka, Schema Registry, Redis, OSRM, Simulation, Stream Processor, Frontend |
| 5 | Monitoring: Prometheus, Loki, Tempo, OTel Collector, cAdvisor, Grafana |
| 6 | Gateway API networking: GatewayClass, Gateway, HTTPRoutes |

## Common Tasks

### Stand up the full platform from scratch

```bash
./infrastructure/kubernetes/scripts/create-cluster.sh
./infrastructure/kubernetes/scripts/deploy-services.sh
./infrastructure/kubernetes/scripts/health-check.sh
./infrastructure/kubernetes/scripts/smoke-test.sh
```

### Use a different cluster name

```bash
CLUSTER_NAME=my-test-cluster ./infrastructure/kubernetes/scripts/create-cluster.sh
CLUSTER_NAME=my-test-cluster ./infrastructure/kubernetes/scripts/deploy-services.sh
CLUSTER_NAME=my-test-cluster ./infrastructure/kubernetes/scripts/teardown.sh
```

### Tear down and preserve data

```bash
BACKUP_DIR=~/rideshare-backups \
  ./infrastructure/kubernetes/scripts/teardown.sh --preserve-data --backup-dir=~/rideshare-backups
```

The script creates `~/rideshare-backups/rideshare-k8s-backup-<YYYYMMDD-HHMMSS>.tar.gz` containing:
- `minio/data.tar.gz` — MinIO object store contents
- `kafka/data.tar.gz` — Kafka log segments
- `airflow-postgres/data.tar.gz` — Airflow Postgres data directory
- `manifests/` — exported YAML for all resources, PVCs, and ConfigMaps

### Re-apply manifests without recreating the cluster

```bash
./infrastructure/kubernetes/scripts/deploy-services.sh
```

The script is safe to re-run; most `kubectl apply` calls are idempotent. StorageClass and Gateway API resource errors are suppressed where re-application would fail due to immutable fields or CRD timing.

### Install ESO manually (if Helm was absent during cluster creation)

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update external-secrets
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace \
  --set installCRDs=true --version 0.11.0 \
  --set 'env[0].name=AWS_ENDPOINT_URL' \
  --set 'env[0].value=http://localstack.default.svc.cluster.local:4566'
```

## Troubleshooting

### `create-cluster.sh` exits immediately without creating a cluster

The cluster already exists. To recreate:

```bash
kind delete cluster --name rideshare-local   # or your $CLUSTER_NAME
./infrastructure/kubernetes/scripts/create-cluster.sh
```

### ESO pods not ready after cluster creation

ESO may still be pulling images. Wait ~2 minutes and check:

```bash
kubectl get pods -n external-secrets
```

ExternalSecrets will not sync until LocalStack is deployed (step 3 of `deploy-services.sh`) and ESO pods are Running.

### `deploy-services.sh` shows "Warning: Kafka/Redis/MinIO pod not ready yet"

This is normal on first deployment — images are still being pulled. Wait a few minutes and run the health check:

```bash
./infrastructure/kubernetes/scripts/health-check.sh
```

### StorageClass "field is immutable" errors in deploy-services.sh

Expected. Kind creates a default StorageClass; re-applying triggers an immutable-field error that is intentionally filtered. The script continues normally.

### Gateway API "no matches for kind" errors

Expected on first deployment if Gateway API CRDs (step 0) have not yet been accepted by the API server. Re-run `deploy-services.sh` after a short wait, or check CRD readiness:

```bash
kubectl get crd gatewayclasses.gateway.networking.k8s.io
```

### Smoke test DNS failures

The DNS test tries `nslookup`, `getent hosts`, and `ping` in sequence. If all three fail for a service, the container image for the test pod may not include any DNS utilities — or the service itself is not running. Check:

```bash
kubectl get pods
kubectl get services
```

### MinIO backup fails during `--preserve-data` teardown

Backup failures are non-fatal (logged as warnings). The cluster is still deleted. Partial backups may exist in `$BACKUP_DIR`.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context for this scripts directory
- [../manifests/CONTEXT.md](../manifests/CONTEXT.md) — Kubernetes manifests applied by `deploy-services.sh`
- [../CONTEXT.md](../CONTEXT.md) — Kubernetes infrastructure overview
