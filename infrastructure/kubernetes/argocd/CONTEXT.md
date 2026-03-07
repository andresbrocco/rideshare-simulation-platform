# CONTEXT.md — ArgoCD

## Purpose

Defines the ArgoCD GitOps configuration for deploying the rideshare platform to production Kubernetes. This includes the upstream ArgoCD installation manifest, the platform's Application resource, and a ConfigMap documenting sync policies across environments.

## Responsibility Boundaries

- **Owns**: ArgoCD Application definition, sync policy documentation, vendored ArgoCD install manifest
- **Delegates to**: `infrastructure/kubernetes/overlays/` for the Kustomize manifests ArgoCD actually deploys
- **Does not handle**: Cluster provisioning, IAM/IRSA, or application-level Kubernetes manifests

## Key Concepts

- **Application resource** (`app-rideshare-platform.yaml`): The ArgoCD CRD that points to a specific Git repo, branch (`deploy`), and Kustomize overlay path. ArgoCD continuously reconciles the cluster state to match that path.
- **deploy branch**: ArgoCD watches the `deploy` branch (not `main`). Merging to `deploy` triggers reconciliation. Manual `kubectl` changes to resources managed by this Application are automatically reverted by `selfHeal: true`.
- **DBT runner overlay selection**: The `path` field in `app-rideshare-platform.yaml` contains a placeholder (`production-<dbt-runner>`) that must be substituted before applying — either `overlays/production-duckdb` or `overlays/production-glue` depending on the active DBT runner.
- **ignoreDifferences**: Replica counts on Deployments and StatefulSets are excluded from drift detection, allowing a Horizontal Pod Autoscaler to scale without ArgoCD reverting replica changes.

## Non-Obvious Details

- `install.yaml` is the vendored upstream ArgoCD install manifest (auto-generated, marked `DO NOT EDIT`). It is pinned at a specific ArgoCD version. Upgrading requires replacing this file with a new upstream release.
- `sync-policy.yaml` is a plain ConfigMap used for human documentation of environment-specific policies — it is not a live ArgoCD sync policy object. The actual sync policy for production is embedded in `app-rideshare-platform.yaml` (`automated.selfHeal: true`, `prune: true`).
- Production has `selfHeal: true` (contrary to what `sync-policy.yaml` documents for prod). The Application manifest is the authoritative source; the ConfigMap reflects an intent that diverged from implementation.
- `resources-finalizer.argocd.argoproj.io` on the Application ensures all managed cluster resources are deleted when the Application itself is deleted (cascade delete). Removing the Application without this finalizer would orphan resources.
- Sync retry is configured with exponential backoff (5s base, factor 2, max 3m, 5 attempts) to handle transient API server errors during large rollouts.

## Related Modules

- [infrastructure/kubernetes/manifests](../manifests/CONTEXT.md) — Reverse dependency — Provides All Deployment, Service, ConfigMap, Secret, PV, PVC, CronJob, HTTPRoute, Gateway, GatewayClass, StorageClass, ExternalSecret resources
- [infrastructure/kubernetes/overlays/production-duckdb](../overlays/production-duckdb/CONTEXT.md) — Dependency — Kustomize production overlay for DBT_RUNNER=duckdb — deploys full platform with ...
- [infrastructure/kubernetes/overlays/production-glue](../overlays/production-glue/CONTEXT.md) — Dependency — Kustomize overlay for the DBT_RUNNER=glue production deployment variant, assembl...
- [infrastructure/kubernetes/tests](../tests/CONTEXT.md) — Reverse dependency — Consumed by this module
