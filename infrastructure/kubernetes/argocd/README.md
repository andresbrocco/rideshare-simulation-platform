# ArgoCD Configuration

This directory contains ArgoCD installation and application manifests for GitOps-based deployment of the rideshare simulation platform.

## Components

### Installation
- `install.yaml` - ArgoCD 3.2.3 installation manifest with all required resources

### Applications
- `app-core-services.yaml` - Core simulation services (simulation, frontend, kafka, redis, etc.)
- `app-data-platform.yaml` - Data platform services (spark, minio, airflow, superset, etc.)

### Configuration
- `sync-policy.yaml` - Sync policy documentation and configuration

## Quick Start

### 1. Install ArgoCD

```bash
kubectl apply -f install.yaml
```

Wait for all ArgoCD pods to be ready:

```bash
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/part-of=argocd -n argocd --timeout=5m
```

### 2. Access ArgoCD UI

Get the initial admin password:

```bash
kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
```

Port-forward to access the UI:

```bash
kubectl port-forward svc/argocd-server -n argocd 8081:443
```

Open browser to: https://localhost:8081

Login with:
- Username: `admin`
- Password: (from secret above)

### 3. Deploy Applications

Deploy core services:

```bash
kubectl apply -f app-core-services.yaml
```

Deploy data platform:

```bash
kubectl apply -f app-data-platform.yaml
```

Apply sync policy configuration:

```bash
kubectl apply -f sync-policy.yaml
```

## ArgoCD CLI Usage

### Install CLI

```bash
brew install argocd
```

### Login

```bash
argocd login localhost:8081 --username admin --password '<password>' --insecure
```

### List Applications

```bash
argocd app list
```

### View Application Status

```bash
argocd app get core-services
argocd app get data-platform
```

### Manual Sync

```bash
argocd app sync core-services
argocd app sync data-platform
```

### View Sync History

```bash
argocd app history core-services
```

## GitOps Workflow

1. Make changes to Kubernetes manifests in `infrastructure/kubernetes/manifests/`
2. Commit and push changes to Git repository
3. ArgoCD detects drift (polls every 3 minutes by default)
4. Auto-sync applies changes automatically (if enabled)
5. Monitor sync status in ArgoCD UI or CLI

## Sync Policies

### Development Environment (Current)
- **Auto-sync**: ENABLED - Changes are automatically applied
- **Self-heal**: ENABLED - Manual changes are automatically reverted
- **Prune**: ENABLED - Deleted resources are removed from cluster

### Production Environment
- **Auto-sync**: DISABLED - Manual approval required
- **Self-heal**: DISABLED - Manual changes not reverted
- **Prune**: ENABLED - Deleted resources removed after manual sync

## Configuration Drift Detection

ArgoCD continuously monitors the cluster state against Git:

- **Reconciliation Interval**: 180 seconds (3 minutes)
- **Detection**: Compares live cluster state with Git manifests
- **Status**: Application marked as "OutOfSync" when drift detected
- **Self-Heal**: Automatically corrects drift if enabled

## Application Structure

### Core Services Application
Includes:
- Simulation engine
- Frontend UI
- Stream processor
- Kafka + Schema Registry
- Redis
- OSRM routing
- Gateway API routing
- ConfigMaps and Secrets

### Data Platform Application
Includes:
- MinIO (object storage)
- LocalStack (AWS emulation)
- Spark (master, worker, thrift-server)
- Airflow (scheduler, webserver, postgres)
- Superset (analytics, postgres, redis)
- Prometheus + Grafana (monitoring)
- Storage classes and PVCs

## Troubleshooting

### Check Application Health

```bash
kubectl get applications -n argocd
```

### View Application Events

```bash
kubectl describe application core-services -n argocd
```

### Force Refresh

```bash
argocd app get core-services --refresh
```

### Hard Refresh (bypass cache)

```bash
argocd app get core-services --hard-refresh
```

### View Sync Status

```bash
argocd app sync core-services --dry-run
```

### Delete and Recreate Application

```bash
kubectl delete application core-services -n argocd
kubectl apply -f app-core-services.yaml
```

## Version Information

- **ArgoCD Version**: 3.2.3 (actually v2.12.3 - latest stable)
- **Installation Source**: Official ArgoCD manifests
- **CRD Version**: argoproj.io/v1alpha1

## Security Notes

- ArgoCD runs in insecure mode (HTTP) for local development
- Change initial admin password after first login
- For production, enable TLS and configure SSO/RBAC
- Repository access uses public HTTPS (no credentials needed for public repos)

## References

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [ArgoCD GitHub](https://github.com/argoproj/argo-cd)
- [Getting Started Guide](https://argo-cd.readthedocs.io/en/stable/getting_started/)
