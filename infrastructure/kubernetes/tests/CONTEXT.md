# CONTEXT.md — Kubernetes Tests

## Purpose

Shell-based integration test suite that validates Kubernetes manifest correctness and cluster behavior by applying resources against a live Kind cluster and asserting expected outcomes. Tests cover the full deployment lifecycle rather than unit-testing configuration files.

## Responsibility Boundaries

- **Owns**: End-to-end validation of Kubernetes manifests, cluster lifecycle scripts, and infrastructure behavior (pod readiness, PVC binding, Gateway routing, ArgoCD sync)
- **Delegates to**: The scripts in `infrastructure/kubernetes/scripts/` for cluster creation, deployment, health checks, and teardown
- **Does not handle**: Application-level correctness (API responses, data correctness) — that belongs to integration tests under `tests/integration/`

## Key Concepts

**Test Scope by File**:
- `test_lifecycle.sh` — Full cluster lifecycle: create → deploy → health-check → smoke-test → teardown with backup verification
- `test_core_services.sh` — Core service manifests (Kafka, Redis, OSRM, simulation, stream-processor, frontend) reach `Ready` state
- `test_data_platform.sh` — Data platform manifests (MinIO, bronze-ingestion, Airflow, Prometheus, Grafana) reach `Ready` state; also validates memory limit values in manifest files match expected allocations
- `test_config_secrets.sh` — ConfigMap and Secret injection validated via a disposable `busybox` test pod with live `kubectl exec` checks
- `test_persistence.sh` — PVC binding verified; data persistence across pod restarts proven via a MinIO write/delete/re-read cycle
- `test_ingress.sh` — Gateway API (Envoy Gateway) installation, HTTPRoute acceptance, and HTTP reachability for all exposed paths including WebSocket
- `test_argocd.sh` — ArgoCD installation, Application creation, and drift detection via intentional replica patch with self-healing assertion
- `setup_static_pvs.sh` — Pre-requisite helper; creates static PVs from `pv-static.yaml` before `test_persistence.sh` can run

## Non-Obvious Details

- `setup_static_pvs.sh` must be run before `test_persistence.sh`; the persistence tests depend on static PVs that are not auto-provisioned in Kind.
- `test_data_platform.sh` performs a textual grep against manifest YAML files to assert memory limit strings (e.g., `"256Mi"`) — if a manifest changes its memory format or quoting style, this test will falsely fail without a real resource problem.
- `test_argocd.sh` includes a live drift detection test: it intentionally patches a managed deployment's replica count and polls for `OutOfSync` status, then verifies self-healing. It gracefully skips this step if no ArgoCD-managed deployments exist yet.
- `test_ingress.sh` downloads and installs Gateway API CRDs and Envoy Gateway from the internet at test time — tests require network access and are not hermetic.
- `test_lifecycle.sh` validates that teardown with `--preserve-data` creates a backup tar in `/tmp/rideshare-k8s-backup-*.tar.gz` within the last 10 minutes, using `stat` with dual-flag handling for macOS vs Linux portability.
- All tests use `set -e` and exit non-zero on any failure, making them suitable for CI use.

## Related Modules

- [infrastructure/kubernetes/argocd](../argocd/CONTEXT.md) — Dependency — ArgoCD GitOps configuration for deploying the rideshare platform to production K...
- [infrastructure/kubernetes/manifests](../manifests/CONTEXT.md) — Dependency — Base Kubernetes manifests for all platform services, infrastructure dependencies...
- [infrastructure/kubernetes/scripts](../scripts/CONTEXT.md) — Dependency — Lifecycle management scripts for the local Kind-based Kubernetes cluster
