# CONTEXT.md — Kubernetes Scripts

## Purpose

Lifecycle management scripts for the local Kind-based Kubernetes cluster. They encapsulate the ordered sequence of operations needed to stand up, verify, and tear down the full platform stack — bridging raw manifest files and operator tooling into a repeatable workflow.

## Responsibility Boundaries

- **Owns**: Cluster creation/deletion, manifest application order, health verification, smoke testing, and optional data backup before teardown
- **Delegates to**: `kubectl` for resource management, `helm` for External Secrets Operator installation, `kind` for cluster lifecycle
- **Does not handle**: Manifest content, image building, CI/CD orchestration, or production cluster management

## Key Concepts

- **External Secrets Operator (ESO)**: Installed via Helm during `create-cluster.sh`. The controller is pointed at `http://localstack.default.svc.cluster.local:4566` via an `AWS_ENDPOINT_URL` env var so it syncs secrets from LocalStack rather than real AWS. ExternalSecret CRDs are applied only after LocalStack is deployed (step 3b in `deploy-services.sh`), since ESO needs a live secrets backend to sync from.
- **Deployment order**: `deploy-services.sh` applies manifests in a strict 6-step sequence: storage → ConfigMaps/Secrets → data platform services → simulation services → monitoring → Gateway API networking. Gateway API CRDs are installed separately (step 0) because they come from an external URL and may already exist.
- **Health check vs. smoke test**: `health-check.sh` checks Kubernetes-level state (node readiness, pod counts, PVC binding). `smoke-test.sh` performs in-cluster functional probes — exec'ing into running pods to verify Kafka broker API responses, Redis PING/PONG, MinIO health endpoint, DNS resolution, and storage write access.

## Non-Obvious Details

- StorageClass application in `deploy-services.sh` uses `set +e` and filters out "field is immutable" errors because Kind creates a default StorageClass and re-applying it raises an immutable field error that would otherwise abort the script.
- Gateway API resources (GatewayClass, Gateway, HTTPRoutes) are applied with `set +e` and suppress "no matches for kind" errors because the CRDs installed in step 0 may not have been accepted by the API server yet.
- `teardown.sh` accepts `--preserve-data` to exec `tar` into MinIO, Kafka, and Airflow Postgres pods before deleting the cluster. The backup is written to `BACKUP_DIR` (default `/tmp`) as a timestamped tarball that also includes exported manifests, PVC definitions, and ConfigMaps.
- `create-cluster.sh` is idempotent — it exits 0 without error if the cluster already exists, and prints guidance to delete manually before recreating.
- Smoke test 4 (DNS resolution) tries three fallback commands (`nslookup`, `getent hosts`, `ping`) because different container images may not have all DNS utilities installed.

## Related Modules

- [infrastructure/kubernetes/manifests](../manifests/CONTEXT.md) — Dependency — Base Kubernetes manifests for all platform services, infrastructure dependencies...
- [infrastructure/kubernetes/tests](../tests/CONTEXT.md) — Reverse dependency — Consumed by this module
