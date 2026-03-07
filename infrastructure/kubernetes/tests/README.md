# Kubernetes Tests

> Shell-based integration test suite that validates Kubernetes manifest correctness and cluster behavior against a live Kind cluster.

## Quick Reference

### Prerequisites

| Tool | Purpose |
|------|---------|
| `kind` | Local Kubernetes cluster (Kind) |
| `kubectl` | Kubernetes CLI |
| `curl` | HTTP endpoint reachability tests |
| `websocat` | WebSocket test (optional — test skips if absent) |

Install `websocat` if needed:

```bash
brew install websocat         # macOS
cargo install websocat        # from source
```

### Test Scripts

| Script | What it tests | Notes |
|--------|--------------|-------|
| `test_lifecycle.sh` | Full cluster lifecycle: create → deploy → health-check → smoke-test → teardown | Runs the lifecycle scripts end-to-end |
| `test_core_services.sh` | Kafka, Redis, OSRM, simulation, stream-processor, frontend reach `Ready` state | |
| `test_data_platform.sh` | MinIO, bronze-ingestion, Airflow, Prometheus, Grafana reach `Ready` state; verifies memory limits in manifests | Grepped against manifest YAML — format-sensitive |
| `test_config_secrets.sh` | ConfigMap and Secret injection via a disposable `busybox` pod with `kubectl exec` | |
| `test_persistence.sh` | PVC binding and MinIO write/delete/re-read cycle | Requires `setup_static_pvs.sh` first |
| `test_ingress.sh` | Gateway API CRDs, Envoy Gateway, HTTPRoute acceptance, HTTP/WebSocket reachability | Downloads from internet — not hermetic |
| `test_argocd.sh` | ArgoCD install, Application creation, drift detection, self-healing | ArgoCD v3.2.3 |
| `setup_static_pvs.sh` | Creates static PVs from `pv-static.yaml` | Run before `test_persistence.sh` |

### Commands

Run all tests from the project root (`/path/to/rideshare-simulation-platform`):

```bash
# Full lifecycle (create cluster, deploy, health-check, smoke-test, teardown)
bash infrastructure/kubernetes/tests/test_lifecycle.sh

# Core service readiness
bash infrastructure/kubernetes/tests/test_core_services.sh

# Data platform readiness + memory limit validation
bash infrastructure/kubernetes/tests/test_data_platform.sh

# ConfigMap and Secret injection
bash infrastructure/kubernetes/tests/test_config_secrets.sh

# PVC binding and data persistence (setup required first)
bash infrastructure/kubernetes/tests/setup_static_pvs.sh
bash infrastructure/kubernetes/tests/test_persistence.sh

# Gateway API and HTTPRoute acceptance
bash infrastructure/kubernetes/tests/test_ingress.sh

# ArgoCD drift detection and self-healing
bash infrastructure/kubernetes/tests/test_argocd.sh
```

### Port-Forwards Used During Tests

The ingress and ArgoCD tests establish temporary port-forwards and clean them up automatically. If a test is interrupted, you may need to kill the process manually:

| Port | Service | Used by |
|------|---------|---------|
| `8080` | Envoy Gateway (HTTP) | `test_ingress.sh` |
| `8081` | ArgoCD server (HTTPS) | `test_argocd.sh` |

```bash
# Kill a stale port-forward on port 8080
kill "$(lsof -Pi :8080 -sTCP:LISTEN -t)"

# Kill a stale port-forward on port 8081
kill "$(lsof -Pi :8081 -sTCP:LISTEN -t)"
```

### Endpoints Verified by Tests

`test_ingress.sh` asserts HTTP 200/3xx responses through the Envoy Gateway on `localhost:8080`:

| Path | Service |
|------|---------|
| `/` | Control panel frontend |
| `/api/health` | Simulation API health check |
| `/airflow/` | Airflow UI |
| `/grafana/` | Grafana UI |
| `/prometheus/` | Prometheus UI |
| `/api/ws` | WebSocket (simulation events) |

### Teardown Backup Verification

`test_lifecycle.sh` verifies that `teardown.sh --preserve-data` creates a backup at `/tmp/rideshare-k8s-backup-*.tar.gz` within the last 10 minutes. To inspect manually:

```bash
ls -lh /tmp/rideshare-k8s-backup-*.tar.gz
```

## Common Tasks

### Run the full suite sequentially

```bash
cd /path/to/rideshare-simulation-platform

bash infrastructure/kubernetes/tests/test_lifecycle.sh
bash infrastructure/kubernetes/tests/setup_static_pvs.sh
bash infrastructure/kubernetes/tests/test_core_services.sh
bash infrastructure/kubernetes/tests/test_data_platform.sh
bash infrastructure/kubernetes/tests/test_config_secrets.sh
bash infrastructure/kubernetes/tests/test_persistence.sh
bash infrastructure/kubernetes/tests/test_ingress.sh
bash infrastructure/kubernetes/tests/test_argocd.sh
```

### Access ArgoCD UI after `test_argocd.sh`

```bash
kubectl port-forward svc/argocd-server -n argocd 8081:443
# Then open: https://localhost:8081
# Username: admin
# Password: kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d
```

### Manual port-forward for data platform services

```bash
kubectl port-forward svc/minio 9001:9001              # MinIO console
kubectl port-forward svc/bronze-ingestion 8086:8080   # Bronze ingestion health
kubectl port-forward svc/airflow-webserver 8082:8082  # Airflow UI
kubectl port-forward svc/prometheus 9090:9090         # Prometheus UI
kubectl port-forward svc/grafana 3001:3001            # Grafana UI
```

## Troubleshooting

**`test_persistence.sh` fails immediately with PVC pending**
Run `setup_static_pvs.sh` first. Kind does not auto-provision static PVs; the test depends on PVs created from `infrastructure/kubernetes/manifests/pv-static.yaml`.

**`test_data_platform.sh` fails memory assertion without a real resource issue**
The test greps manifest YAML for `memory: "<value>"` (with double-quotes). If a manifest was reformatted to use `memory: <value>` without quotes, the grep will fail even though the limit is correct. Update the manifest quoting style to match `"256Mi"` format.

**`test_ingress.sh` fails with network errors**
This test downloads Gateway API CRDs and Envoy Gateway from GitHub at runtime. It is not hermetic and requires internet access. Retry if the download timed out.

**`test_ingress.sh` fails: `Could not find Envoy Gateway service`**
The Envoy Gateway service name includes a hash suffix. Wait for the gateway to fully reconcile and retry. Check status with:

```bash
kubectl get svc -n envoy-gateway-system
kubectl get gateway rideshare-gateway
```

**`test_argocd.sh` skip on drift test**
If no ArgoCD-managed deployments exist yet (applications haven't synced), the drift test is gracefully skipped. This is expected on a freshly created cluster before any sync completes.

**Port already in use when test starts**
Both `test_ingress.sh` and `test_argocd.sh` attempt to kill existing processes on their test ports (8080 and 8081) before starting. If that auto-kill fails, terminate manually (see Port-Forwards section above).

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context for this test suite
- [infrastructure/kubernetes/scripts](../scripts) — Lifecycle scripts exercised by `test_lifecycle.sh`
- [infrastructure/kubernetes/manifests](../manifests) — Manifests applied and validated by these tests
- [infrastructure/kubernetes/argocd](../argocd) — ArgoCD configuration tested by `test_argocd.sh`
