# CONTEXT.md — Kubernetes Scripts

## Purpose

Lifecycle management scripts for local Kind cluster operations. Provides idempotent cluster creation, ordered service deployment, comprehensive health validation, and data-preserving teardown.

## Responsibility Boundaries

- **Owns**: Kind cluster lifecycle (create/destroy), manifest deployment orchestration, infrastructure health validation, PVC backup/restore
- **Delegates to**: kubectl for Kubernetes API operations, Kind CLI for cluster management, individual manifests for service configuration
- **Does not handle**: Service-level configuration (delegated to ConfigMaps), cloud provider operations (Terraform), application deployment (ArgoCD in production)

## Key Concepts

**Deployment Order**: Scripts enforce dependency-aware deployment: storage resources → secrets/configmaps → data platform (MinIO, Spark, Airflow, Superset) → core simulation services (Kafka, Redis, OSRM) → networking (Gateway API). This prevents initialization race conditions.

**Graceful Degradation**: Non-critical failures (StorageClass immutability, Gateway API CRDs, optional service pods) are logged but don't fail the deployment. Critical services (Kafka, Redis, MinIO) must pass health checks.

**Data Preservation**: Teardown script supports `--preserve-data` flag that exports PVC contents and manifests to a timestamped tarball before cluster deletion.

## Non-Obvious Details

- **StorageClass Immutability**: `deploy-services.sh` suppresses "field is immutable" errors because Kind may pre-create a default StorageClass that conflicts with custom definitions.

- **Gateway API CRDs**: Gateway API resources (GatewayClass, Gateway, HTTPRoute) may fail if CRDs aren't ready. Scripts use `set +e` and filter stderr to prevent false failures while CRDs initialize asynchronously.

- **Health Check Leniency**: Unbound PVCs don't fail health checks in Kind environments because static PVs may bind asynchronously. Failed pods are logged as warnings if they're non-critical.

- **Backup Mechanics**: `teardown.sh --preserve-data` uses `kubectl exec` with tar to extract data from running pods before cluster deletion. This avoids PV mount issues after teardown.

- **Script Portability**: All scripts resolve `PROJECT_ROOT` via `SCRIPT_DIR` navigation to support execution from any working directory.

## Related Modules

- **[infrastructure/kubernetes/manifests](../manifests/CONTEXT.md)** — Deploys these resource definitions with dependency-aware ordering
- **[infrastructure/kubernetes/overlays](../overlays/CONTEXT.md)** — Applies overlay patches during deployment via kustomize build
