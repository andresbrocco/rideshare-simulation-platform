# CONTEXT.md — Kubernetes

## Purpose

Provides Kubernetes deployment configurations and tooling for running the rideshare simulation platform on both local Kind clusters and cloud environments. Implements GitOps patterns via ArgoCD and environment-specific overlays via Kustomize.

## Responsibility Boundaries

- **Owns**: Kubernetes manifests for all services, Kind cluster configuration, deployment lifecycle scripts, ArgoCD application definitions, environment overlays (local/production)
- **Delegates to**: Docker images (built elsewhere), service application logic, cloud-specific infrastructure (Terraform)
- **Does not handle**: Docker image building, cloud provisioning (handled by `infrastructure/terraform/`), Docker Compose orchestration (handled by `infrastructure/docker/`)

## Key Concepts

**Kind Cluster**: Local Kubernetes cluster (3 nodes: 1 control-plane + 2 workers) running in Docker containers. Used for cloud parity testing and validating K8s manifests before production deployment.

**ArgoCD GitOps**: Continuous deployment system that monitors Git repository for manifest changes and automatically syncs cluster state. Development environment uses auto-sync with self-healing; production requires manual approval.

**Kustomize Overlays**: Base manifests in `base/` directory with environment-specific patches in `overlays/local` and `overlays/production`. Overlays modify resource limits, storage backends, and service exposure methods.

**Deployment Order**: Storage resources → ConfigMaps/Secrets → Data platform services → Core simulation services → Networking (Gateway API). Order ensures dependencies are satisfied before dependent services start.

**Gateway API**: Modern ingress replacement using GatewayClass, Gateway, and HTTPRoute resources. Routes traffic to services via http://localhost/ paths (e.g., `/api/` → simulation, `/airflow/` → airflow).

**Init Containers**: Manifests use init containers to wait for dependencies (e.g., simulation waits for Kafka, Schema Registry, Redis, OSRM) before main container starts, preventing crash loops.

## Non-Obvious Details

**Resource Budget**: Kind cluster configured for 10GB total Docker memory (1GB control plane, 4.5GB per worker, 1GB system overhead). Local overlays use smaller resource limits suitable for laptop development.

**Static PVs**: Uses static PersistentVolumes (`pv-static.yaml`) pre-created for predictable storage allocation in Kind clusters. Production would use dynamic provisioning via StorageClass.

**Two Sync Policies**: ArgoCD applications configured differently per environment - development has auto-sync enabled for rapid iteration, production requires manual sync for change control.

**Profile-Like Organization**: Services grouped into logical applications (core-services, data-pipeline) mirroring Docker Compose profiles, allowing selective deployment.

**Health Scripts Don't Fail Fast**: Health check and smoke test scripts collect all failures before exiting to provide complete diagnostic output rather than stopping at first error.

## Related Modules

- **[infrastructure/kubernetes/manifests](./manifests/CONTEXT.md)** — Contains the actual Kubernetes resource definitions deployed by this module's lifecycle scripts
- **[infrastructure/kubernetes/scripts](./scripts/CONTEXT.md)** — Lifecycle management automation for cluster creation, deployment, health validation, and teardown
- **[infrastructure/kubernetes/overlays](./overlays/CONTEXT.md)** — Environment-specific customizations via Kustomize for local and production deployments
- **[infrastructure/monitoring](../monitoring/CONTEXT.md)** — Deploys alongside K8s services to provide cluster and service-level observability
