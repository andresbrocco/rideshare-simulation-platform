# infrastructure/kubernetes

> Kubernetes deployment configurations and tooling for running the rideshare simulation platform on Kind clusters

## Quick Reference

### Commands

```bash
# Cluster Management
bash infrastructure/kubernetes/scripts/create-cluster.sh      # Create Kind cluster with ESO
bash infrastructure/kubernetes/scripts/deploy-services.sh     # Deploy all services
bash infrastructure/kubernetes/scripts/health-check.sh        # Check cluster health
bash infrastructure/kubernetes/scripts/smoke-test.sh          # Run connectivity tests
bash infrastructure/kubernetes/scripts/teardown.sh            # Delete cluster
bash infrastructure/kubernetes/scripts/teardown.sh --preserve-data  # Delete cluster with backup

# Direct kubectl commands
kubectl get pods                                              # List all pods
kubectl get nodes                                             # List nodes
kubectl logs <pod-name>                                       # View pod logs
kubectl exec -it <pod-name> -- /bin/bash                      # Shell into pod
```

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `CLUSTER_NAME` | Kind cluster name | `rideshare-local` | No |
| `BACKUP_DIR` | Backup directory for teardown | `/tmp` | No |

### Configuration Files

| File | Purpose |
|------|---------|
| `kind/cluster-config.yaml` | Kind cluster configuration (3 nodes: 1 control plane, 2 workers) |
| `manifests/*.yaml` | Kubernetes manifests for all services |
| `overlays/*/kustomization.yaml` | Kustomize overlays for different environments |
| `argocd/applications/*.yaml` | ArgoCD Application definitions |

### Service Ports

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Simulation API | 8000 | HTTP | REST API and WebSocket |
| Stream Processor | 8080 | HTTP | Health and metrics |
| Frontend | 80 | HTTP | Web UI (nginx) |
| Kafka | 9092 | TCP | Broker (internal) |
| Kafka | 29092 | TCP | External listener |
| Redis | 6379 | TCP | Cache and state |
| MinIO | 9000 | HTTP | S3 API |
| MinIO Console | 9001 | HTTP | Admin UI |
| Schema Registry | 8081 | HTTP | Avro schema management |
| Prometheus | 9090 | HTTP | Metrics scraping |
| Grafana | 3001 | HTTP | Dashboards |
| Loki | 3100 | HTTP | Log ingestion |
| Tempo | 3200 | HTTP | Trace ingestion |
| OTEL Collector | 4317 | gRPC | OTLP traces/metrics |
| OTEL Collector | 4318 | HTTP | OTLP traces/metrics |
| Trino | 8080 | HTTP | SQL query engine |
| Airflow Webserver | 8080 | HTTP | Workflow UI |
| Hive Metastore | 9083 | Thrift | Catalog service |
| LocalStack | 4566 | HTTP | AWS API emulation |
| OSRM | 5000 | HTTP | Routing service |

### NodePort Mappings (Kind)

| Host Port | Container Port | Purpose |
|-----------|----------------|---------|
| 80 | 80 | HTTP Ingress |
| 443 | 443 | HTTPS Ingress |
| 30000 | 30000 | NodePort range start |
| 30001 | 30001 | NodePort range |

## Prerequisites

- **Docker Desktop**: 10GB+ RAM allocation
- **kind**: v0.20.0+ (`brew install kind` or https://kind.sigs.k8s.io/)
- **kubectl**: v1.28.0+ (`brew install kubectl`)
- **Helm**: v3.12.0+ (for External Secrets Operator) (`brew install helm`)

## Common Tasks

### Create and Deploy Full Stack

```bash
# 1. Create cluster (3 nodes + ESO)
bash infrastructure/kubernetes/scripts/create-cluster.sh

# 2. Deploy all services
bash infrastructure/kubernetes/scripts/deploy-services.sh

# 3. Verify health
bash infrastructure/kubernetes/scripts/health-check.sh

# 4. Run smoke tests
bash infrastructure/kubernetes/scripts/smoke-test.sh

# 5. Check pod status
kubectl get pods -o wide
```

### Access Services

```bash
# Port-forward to access services locally
kubectl port-forward svc/simulation 8000:8000      # Simulation API
kubectl port-forward svc/frontend 3000:80          # Frontend
kubectl port-forward svc/grafana 3001:3001         # Grafana
kubectl port-forward svc/minio 9000:9000           # MinIO S3
kubectl port-forward svc/minio 9001:9001           # MinIO Console

# Access via NodePort (if configured)
curl http://localhost:30000
```

### View Logs

```bash
# Tail logs for a service
kubectl logs -f deployment/simulation
kubectl logs -f deployment/stream-processor
kubectl logs -f deployment/bronze-ingestion

# View logs from all pods with a label
kubectl logs -l app=simulation --all-containers=true -f

# View logs from specific pod
POD_NAME=$(kubectl get pods -l app=kafka --no-headers | awk '{print $1}' | head -n 1)
kubectl logs -f $POD_NAME
```

### Debug Pods

```bash
# Describe pod (shows events, status, resource usage)
kubectl describe pod <pod-name>

# Get pod YAML
kubectl get pod <pod-name> -o yaml

# Shell into running pod
kubectl exec -it <pod-name> -- /bin/bash

# Run command in pod
kubectl exec -i <pod-name> -- env
kubectl exec -i <pod-name> -- curl http://localhost:8000/health
```

### Check Storage

```bash
# List PersistentVolumeClaims
kubectl get pvc

# List PersistentVolumes
kubectl get pv

# Describe PVC (shows binding status)
kubectl describe pvc minio-storage
```

### Manage Secrets (External Secrets Operator)

```bash
# Check ESO installation
kubectl get pods -n external-secrets

# List SecretStores
kubectl get secretstore

# List ExternalSecrets
kubectl get externalsecret

# Describe ExternalSecret (shows sync status)
kubectl describe externalsecret api-keys

# View synced Kubernetes Secret
kubectl get secret api-keys -o yaml
```

### Scale Deployments

```bash
# Scale simulation service
kubectl scale deployment simulation --replicas=2

# Scale stream processor
kubectl scale deployment stream-processor --replicas=3

# Check current replicas
kubectl get deployment
```

### Cleanup and Teardown

```bash
# Delete cluster (no backup)
bash infrastructure/kubernetes/scripts/teardown.sh

# Delete cluster with data backup
bash infrastructure/kubernetes/scripts/teardown.sh --preserve-data

# Delete cluster with custom backup location
BACKUP_DIR=/path/to/backups bash infrastructure/kubernetes/scripts/teardown.sh --preserve-data

# Manual cleanup (if script fails)
kind delete cluster --name rideshare-local
```

## Deployment Order

The `deploy-services.sh` script deploys resources in dependency order:

1. **Storage**: StorageClass, PersistentVolumes, PersistentVolumeClaims
2. **Configuration**: ConfigMaps, Secrets, External Secrets Operator resources
3. **Data Platform**: MinIO, LocalStack, Postgres, Hive Metastore, Trino, Airflow
4. **Core Services**: Kafka, Schema Registry, Redis, OSRM, Simulation, Stream Processor, Frontend
5. **Monitoring**: Prometheus, Loki, Tempo, OTEL Collector, cAdvisor, Grafana
6. **Networking**: Gateway API resources (GatewayClass, Gateway, HTTPRoutes)

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `Cluster not accessible` | Kind cluster not running | Run `kind get clusters` to verify, recreate with `create-cluster.sh` |
| `Pods stuck in Pending` | Resource limits or PVC binding issues | Check `kubectl describe pod <name>` for events, verify PVCs with `kubectl get pvc` |
| `ImagePullBackOff` | Docker images not available locally | Build images with Docker Compose first or use Kind's image loading |
| `CrashLoopBackOff` | Application crash on startup | Check logs with `kubectl logs <pod>`, verify dependencies are running |
| `ExternalSecret not syncing` | LocalStack not running or wrong endpoint | Verify LocalStack pod is running, check ESO controller logs |
| `Service DNS not resolving` | CoreDNS issues | Check `kubectl get pods -n kube-system`, restart CoreDNS if needed |
| `PVC not binding` | No available PersistentVolumes | Verify PVs exist with `kubectl get pv`, check PVC/PV storageClassName matches |
| `ESO Helm install fails` | Helm not installed | Install Helm: `brew install helm` or https://helm.sh/docs/intro/install/ |
| `Nodes not Ready` | Docker Desktop resource limits | Increase Docker Desktop memory to 10GB+, restart Docker |
| `Port-forward fails` | Pod not running or wrong port | Verify pod is Running with `kubectl get pods`, check service port with `kubectl get svc` |

## Related

- [CONTEXT.md](CONTEXT.md) — Kubernetes architecture and GitOps patterns
- [../docker/README.md](../docker/README.md) — Docker Compose alternative
- [scripts/README.md](scripts/README.md) — Script documentation
- [manifests/README.md](manifests/README.md) — Manifest organization
