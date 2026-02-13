# Kubernetes Scripts

> Lifecycle management scripts for local Kind cluster operations with idempotent creation, ordered deployment, and data-preserving teardown.

## Quick Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLUSTER_NAME` | `rideshare-local` | Name of the Kind cluster |
| `BACKUP_DIR` | `/tmp` | Directory for data backups during teardown |

### Commands

#### Cluster Creation
```bash
# Create Kind cluster with ingress and External Secrets Operator
bash infrastructure/kubernetes/scripts/create-cluster.sh

# Create cluster with custom name
CLUSTER_NAME=my-cluster bash infrastructure/kubernetes/scripts/create-cluster.sh
```

#### Service Deployment
```bash
# Deploy all services to existing cluster
bash infrastructure/kubernetes/scripts/deploy-services.sh
```

Deployment order enforced by script:
1. Storage resources (StorageClass, PVs, PVCs)
2. ConfigMaps and Secrets
3. Data platform services (MinIO, Spark, Airflow, Superset)
4. Core simulation services (Kafka, Redis, OSRM, simulation, stream-processor)
5. Networking (Gateway API resources)

#### Health Validation
```bash
# Check cluster and pod health
bash infrastructure/kubernetes/scripts/health-check.sh

# Run smoke tests (Kafka, Redis, MinIO connectivity)
bash infrastructure/kubernetes/scripts/smoke-test.sh
```

#### Cluster Teardown
```bash
# Destroy cluster without preserving data
bash infrastructure/kubernetes/scripts/teardown.sh

# Preserve data before teardown (exports PVCs to tarball)
bash infrastructure/kubernetes/scripts/teardown.sh --preserve-data

# Custom backup location
bash infrastructure/kubernetes/scripts/teardown.sh --preserve-data --backup-dir=/path/to/backups
```

### Prerequisites

- **Docker Desktop** or Docker Engine (10GB+ memory recommended)
- **Kind** - Kubernetes in Docker ([installation](https://kind.sigs.k8s.io/docs/user/quick-start/#installation))
- **kubectl** - Kubernetes CLI ([installation](https://kubernetes.io/docs/tasks/tools/))
- **Helm** (optional) - Required for External Secrets Operator installation ([installation](https://helm.sh/docs/intro/install/))

Check installation:
```bash
docker --version
kind --version
kubectl version --client
helm version  # optional
```

### Configuration

All scripts resolve paths via `SCRIPT_DIR` and support execution from any working directory.

**Kind Cluster Configuration**: `infrastructure/kubernetes/kind/cluster-config.yaml`
- 1 control-plane node + 2 worker nodes
- Port mappings: 80 (HTTP), 443 (HTTPS), 30000-30001 (NodePort)
- Resource budget: 10GB total (1GB control plane, 4.5GB per worker)

**Kubernetes Manifests**: `infrastructure/kubernetes/manifests/`
- Base manifests for all services
- StorageClass, PVs, PVCs for persistent storage
- ConfigMaps and Secrets for service configuration

## Common Tasks

### Initial Cluster Setup

```bash
# 1. Create cluster
bash infrastructure/kubernetes/scripts/create-cluster.sh

# 2. Deploy all services
bash infrastructure/kubernetes/scripts/deploy-services.sh

# 3. Verify deployment
bash infrastructure/kubernetes/scripts/health-check.sh
bash infrastructure/kubernetes/scripts/smoke-test.sh
```

### Check Service Status

```bash
# List all pods
kubectl get pods

# Check specific service
kubectl get pods -l app=simulation
kubectl logs -l app=simulation -f

# Check persistent volumes
kubectl get pv
kubectl get pvc
```

### Access Services

```bash
# Via Gateway API (after deployment)
curl http://localhost/api/health

# Via NodePort (direct service access)
kubectl get svc -o wide

# Port forward to specific service
kubectl port-forward svc/simulation 8000:8000
```

### Troubleshoot Deployment Issues

```bash
# Check pod events
kubectl describe pod <pod-name>

# View pod logs
kubectl logs <pod-name>
kubectl logs <pod-name> --previous  # previous container instance

# Check node resources
kubectl top nodes
kubectl top pods

# Verify External Secrets Operator
kubectl get pods -n external-secrets
kubectl logs -n external-secrets -l app.kubernetes.io/name=external-secrets
```

### Recreate Cluster

```bash
# Delete existing cluster
kind delete cluster --name rideshare-local

# Create fresh cluster
bash infrastructure/kubernetes/scripts/create-cluster.sh
bash infrastructure/kubernetes/scripts/deploy-services.sh
```

## Troubleshooting

### Cluster Creation Fails

**Symptom**: `create-cluster.sh` fails with "cluster already exists"

**Solution**:
```bash
# Delete existing cluster first
kind delete cluster --name rideshare-local

# Then recreate
bash infrastructure/kubernetes/scripts/create-cluster.sh
```

### Helm Not Found During ESO Installation

**Symptom**: "Warning: Helm not found. Skipping ESO installation."

**Solution**: ESO installation is optional for local development. To install manually:
```bash
# Install Helm (macOS)
brew install helm

# Install ESO
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets --create-namespace \
  --set installCRDs=true --version 0.11.0 \
  --set "env[0].name=AWS_ENDPOINT_URL" \
  --set "env[0].value=http://localstack.default.svc.cluster.local:4566"
```

### Pods Stuck in Pending State

**Symptom**: Pods show `Pending` status indefinitely

**Possible Causes**:
- Insufficient node resources
- PVC waiting for PV binding
- Image pull issues

**Diagnosis**:
```bash
kubectl describe pod <pod-name>
kubectl get events --sort-by='.lastTimestamp'
```

### StorageClass "Immutable Field" Errors

**Symptom**: Deployment fails with "field is immutable" error for StorageClass

**Expected**: This is normal - `deploy-services.sh` suppresses these errors because Kind pre-creates a default StorageClass that may conflict. The script continues deployment successfully.

### Gateway API Resources Fail to Apply

**Symptom**: HTTPRoute or Gateway resources fail with "CRD not found"

**Expected**: Gateway API CRDs may initialize asynchronously. The script uses `set +e` to prevent false failures. Resources will be created once CRDs are ready.

**Verify**:
```bash
kubectl get crd | grep gateway
kubectl get gatewayclass
kubectl get gateway
```

### Health Check Shows Failed Pods

**Symptom**: `health-check.sh` reports failed pods

**Diagnosis**: Non-critical service failures are logged as warnings. Critical services (Kafka, Redis, MinIO) must pass for smoke tests to succeed.

```bash
# Check which pods failed
kubectl get pods --field-selector=status.phase!=Running,status.phase!=Succeeded

# Investigate specific pod
kubectl describe pod <failed-pod-name>
kubectl logs <failed-pod-name>
```

### Data Preservation During Teardown

**Symptom**: Need to save data before destroying cluster

**Solution**:
```bash
# Backup PVCs to timestamped tarball
bash infrastructure/kubernetes/scripts/teardown.sh --preserve-data --backup-dir=/path/to/backups

# Backup created at: /path/to/backups/rideshare-k8s-backup-YYYYMMDD-HHMMSS.tar.gz
```

## Related

- [../CONTEXT.md](../CONTEXT.md) — Kubernetes deployment architecture and patterns
- [../manifests/](../manifests/) — Service manifests and configurations
- [../kind/cluster-config.yaml](../kind/cluster-config.yaml) — Kind cluster specification
- [../../docker/compose.yml](../../docker/compose.yml) — Alternative Docker Compose deployment

---
