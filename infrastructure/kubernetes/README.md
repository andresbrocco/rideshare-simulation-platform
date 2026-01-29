# Kubernetes

> Kubernetes deployment configurations and tooling for local and cloud environments

## Quick Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `CLUSTER_NAME` | Name of the Kind cluster | `rideshare-local` | No |
| `PRESERVE_DATA` | Backup PVCs before teardown | `false` | No |
| `BACKUP_DIR` | Directory for cluster backups | `/tmp` | No |

### Commands

```bash
# Cluster Lifecycle
./infrastructure/kubernetes/scripts/create-cluster.sh
  # Creates Kind cluster with 3 nodes (1 control-plane + 2 workers)
  # Configures port mappings for Ingress (80, 443)
  # Waits for nodes to be Ready

./infrastructure/kubernetes/scripts/deploy-services.sh
  # Deploys all Kubernetes manifests in order:
  # 1. Storage (StorageClass, PVs, PVCs)
  # 2. Config/Secrets (ConfigMaps, Secrets)
  # 3. Data platform (MinIO, Spark, Airflow, Superset, LocalStack)
  # 4. Core services (Kafka, Redis, OSRM, Simulation, Stream Processor, Frontend)
  # 5. Monitoring (Prometheus, Grafana)
  # 6. Networking (Gateway API resources)

./infrastructure/kubernetes/scripts/health-check.sh
  # Validates cluster health
  # Checks node status
  # Verifies critical services (Kafka, Redis, MinIO)
  # Confirms PVC bindings

./infrastructure/kubernetes/scripts/smoke-test.sh
  # Runs connectivity tests for Kafka, Redis, MinIO
  # Tests DNS resolution for services
  # Validates persistent storage read/write

./infrastructure/kubernetes/scripts/teardown.sh [--preserve-data] [--backup-dir=/path]
  # Deletes Kind cluster
  # Optional: --preserve-data backs up PVC data before deletion
  # Optional: --backup-dir=/path specifies backup location
```

### Configuration Files

| File | Purpose |
|------|---------|
| `kind/cluster-config.yaml` | Kind cluster definition (3 nodes, port mappings, network config) |
| `manifests/*.yaml` | Kubernetes resource definitions for all services |
| `argocd/*.yaml` | ArgoCD application definitions and sync policies |
| `overlays/local/kustomization.yaml` | Local environment customizations |
| `overlays/production/kustomization.yaml` | Production environment customizations |
| `base/core/kustomization.yaml` | Base core services manifest list |
| `base/data-pipeline/kustomization.yaml` | Base data pipeline manifest list |

### Service Access

**Ingress (http://localhost/):**
- Frontend: http://localhost/
- Simulation API: http://localhost/api/
- Airflow: http://localhost/airflow/
- Grafana: http://localhost/grafana/

**Port Forwarding:**
```bash
# ArgoCD UI (HTTPS)
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Access at: https://localhost:8080

# Direct service access
kubectl port-forward svc/simulation 8000:8000
kubectl port-forward svc/kafka 9092:9092
kubectl port-forward svc/redis 6379:6379
```

**NodePort (mapped to localhost):**
- Port 30000: Available for NodePort services
- Port 30001: Available for NodePort services

### Prerequisites

- Docker Desktop (or Docker Engine)
- Kind CLI: `brew install kind` (macOS) or see [Kind installation](https://kind.sigs.k8s.io/docs/user/quick-start/#installation)
- kubectl CLI: `brew install kubectl` (macOS) or see [kubectl installation](https://kubernetes.io/docs/tasks/tools/)
- 10GB available Docker memory (configured in Docker Desktop preferences)

## Common Tasks

### Create and Deploy Full Stack

```bash
# 1. Create Kind cluster
./infrastructure/kubernetes/scripts/create-cluster.sh

# 2. Deploy all services
./infrastructure/kubernetes/scripts/deploy-services.sh

# 3. Verify health
./infrastructure/kubernetes/scripts/health-check.sh

# 4. Run smoke tests
./infrastructure/kubernetes/scripts/smoke-test.sh

# 5. Access services via Ingress
open http://localhost/
```

### Check Deployment Status

```bash
# View all pods
kubectl get pods -o wide

# View services
kubectl get svc

# View PersistentVolumeClaims
kubectl get pvc

# View Gateway API resources
kubectl get gateway,httproute

# View logs for specific service
kubectl logs -f deployment/simulation
kubectl logs -f deployment/stream-processor

# View events
kubectl get events --sort-by='.lastTimestamp'
```

### Redeploy Single Service

```bash
# Update manifest
vim infrastructure/kubernetes/manifests/simulation.yaml

# Apply changes
kubectl apply -f infrastructure/kubernetes/manifests/simulation.yaml

# Watch rollout
kubectl rollout status deployment/simulation
```

### Backup and Restore Data

```bash
# Teardown with data preservation
./infrastructure/kubernetes/scripts/teardown.sh --preserve-data --backup-dir=/path/to/backups

# Backup file created at: /path/to/backups/rideshare-k8s-backup-YYYYMMDD-HHMMSS.tar.gz

# To restore:
# 1. Create new cluster
./infrastructure/kubernetes/scripts/create-cluster.sh

# 2. Deploy services
./infrastructure/kubernetes/scripts/deploy-services.sh

# 3. Restore data (manual process - extract tarball and copy to PVCs)
tar xzf /path/to/backups/rideshare-k8s-backup-YYYYMMDD-HHMMSS.tar.gz
```

### Debug Failed Pods

```bash
# Describe pod to see events
kubectl describe pod <pod-name>

# View logs (current and previous container)
kubectl logs <pod-name>
kubectl logs <pod-name> --previous

# Execute into running pod
kubectl exec -it <pod-name> -- /bin/bash

# Check init container logs
kubectl logs <pod-name> -c <init-container-name>
```

### Update ArgoCD Applications

```bash
# Install ArgoCD (if not already installed)
kubectl apply -f infrastructure/kubernetes/argocd/install.yaml

# Deploy ArgoCD applications
kubectl apply -f infrastructure/kubernetes/argocd/app-core-services.yaml
kubectl apply -f infrastructure/kubernetes/argocd/app-data-pipeline.yaml

# Access ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Get admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# Sync applications via CLI
kubectl patch application core-services -n argocd --type merge -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"HEAD"}}}'
```

### Adjust Resource Limits

```bash
# Edit Kustomize overlay for local environment
vim infrastructure/kubernetes/overlays/local/kustomization.yaml

# Apply overlay
kubectl apply -k infrastructure/kubernetes/overlays/local
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| Cluster creation fails | Kind binary not found | Install Kind: `brew install kind` |
| Pods stuck in Pending | PVC not bound | Check PV availability: `kubectl get pv,pvc` |
| Pods in ImagePullBackOff | Image not available in Kind | Load image: `kind load docker-image <image> --name rideshare-local` |
| Gateway resources fail to apply | Gateway API CRDs not installed | Script auto-installs, but can manually run: `kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.0.0/standard-install.yaml` |
| Init containers timeout | Dependency service not ready | Check dependency pod status: `kubectl get pods -l app=<dependency>` |
| Cannot connect to http://localhost/ | Ingress not configured | Verify Gateway is Programmed: `kubectl get gateway rideshare-gateway` |
| Health check fails | Services still starting | Wait 2-3 minutes for all pods to be Running, then rerun health-check.sh |
| Smoke tests fail | Network connectivity issue | Check service DNS: `kubectl exec -it <pod> -- nslookup <service>` |
| Out of memory errors | Docker Desktop memory too low | Increase Docker memory to 10GB in Docker Desktop preferences |
| StorageClass immutable error | Attempting to modify existing StorageClass | Expected - Kind creates default StorageClass, script continues |

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context and design decisions
- [manifests/CONTEXT.md](manifests/CONTEXT.md) — Kubernetes resource definitions
- [scripts/CONTEXT.md](scripts/CONTEXT.md) — Lifecycle management automation
- [overlays/CONTEXT.md](overlays/CONTEXT.md) — Environment-specific customizations
- [../docker/README.md](../docker/README.md) — Docker Compose alternative deployment
- [../terraform/README.md](../terraform/README.md) — Cloud infrastructure provisioning

---

## Architecture Notes

### Deployment Order

Services are deployed in strict order to satisfy dependencies:

1. **Storage Layer** — StorageClass, PersistentVolumes, PersistentVolumeClaims
2. **Configuration** — ConfigMaps (environment variables), Secrets (credentials, API keys)
3. **Data Platform** — MinIO, Spark (master/worker/thrift-server), Airflow (postgres/scheduler/webserver), Superset (postgres/redis/app), LocalStack
4. **Core Services** — Kafka, Schema Registry, Redis, OSRM, Simulation, Stream Processor, Frontend
5. **Monitoring** — Prometheus, Grafana
6. **Networking** — GatewayClass, Gateway, HTTPRoute resources

### Resource Allocation

**Kind Cluster Budget (10GB total):**
- Control plane node: ~1GB
- Worker node 1: ~4.5GB
- Worker node 2: ~4.5GB
- System overhead: ~1GB

**Local vs Production:**
- Local overlays use smaller resource limits suitable for laptop development
- Production overlays use autoscaling and higher resource requests/limits

### Static vs Dynamic Provisioning

**Local (Kind):**
- Uses static PersistentVolumes pre-created in `pv-static.yaml`
- Predictable storage allocation for development
- PVCs bind to pre-created PVs by matching capacity and access mode

**Production (Cloud):**
- Uses dynamic provisioning via StorageClass (e.g., EBS, GCE PD)
- PVs created on-demand when PVCs are created
- Managed by cloud provider's CSI driver

### Init Containers Pattern

All service manifests use init containers to wait for dependencies before starting the main container:

```yaml
initContainers:
  - name: wait-for-kafka
    image: busybox:1.36
    command: ['sh', '-c', 'until nc -z kafka 9092; do sleep 2; done']
```

This prevents crash loops and ensures clean startup order.

### Gateway API vs Ingress

This deployment uses **Gateway API** (v1.0.0) instead of traditional Ingress:
- **GatewayClass**: Defines gateway controller (Envoy Gateway)
- **Gateway**: Listener configuration (HTTP on port 80)
- **HTTPRoute**: Path-based routing to services

Benefits: More expressive routing, role-oriented design, portable across implementations.

### ArgoCD GitOps

**Development:**
- Auto-sync enabled for rapid iteration
- Self-healing when cluster state drifts from Git
- Application definitions in `argocd/app-*.yaml`

**Production:**
- Manual sync required for change control
- Sync waves for ordered deployment
- Sync policies in `argocd/sync-policy.yaml`

### Kustomize Organization

```
base/
  core/kustomization.yaml          # Core services manifest list
  data-pipeline/kustomization.yaml # Data platform manifest list
overlays/
  local/kustomization.yaml         # Local env patches (smaller resources)
  production/kustomization.yaml    # Production env patches (autoscaling, higher limits)
```

Apply with: `kubectl apply -k infrastructure/kubernetes/overlays/local`
