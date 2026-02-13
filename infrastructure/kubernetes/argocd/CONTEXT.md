# CONTEXT.md — ArgoCD

## Purpose

Implements GitOps-based continuous deployment for the rideshare simulation platform using ArgoCD. Monitors the Git repository for Kubernetes manifest changes and automatically syncs cluster state, enabling declarative infrastructure management with drift detection and self-healing capabilities.

## Responsibility Boundaries

- **Owns**: ArgoCD installation manifests, Application resource definitions (core-services, data-pipeline), sync policy configurations, GitOps workflow documentation
- **Delegates to**: Actual Kubernetes manifests in `infrastructure/kubernetes/manifests/`, Docker images for services, Git repository as source of truth
- **Does not handle**: Building or defining service manifests (those live in `../manifests/`), cluster provisioning (handled by `../scripts/`), application logic

## Key Concepts

**Application Resources**: ArgoCD's CRD for defining what to deploy. Each Application points to a Git repository path, specifies which manifests to include, and defines sync behavior. This module uses two Applications: `core-services` (simulation runtime) and `data-pipeline` (analytics stack).

**Sync Policies**: Control how ArgoCD responds to Git changes and cluster drift. Development uses auto-sync with self-healing (changes applied immediately, manual edits reverted). Production disables auto-sync (manual approval required) but enables pruning for deleted resources.

**Drift Detection**: ArgoCD polls the Git repository every 180 seconds, compares live cluster state against Git manifests, and marks Applications as OutOfSync when differences are detected. Self-heal policy determines whether drift is automatically corrected.

**Directory Source with Include**: Applications use directory source mode with explicit file inclusion rather than pointing to individual files. This allows selective deployment of manifests from the shared `../manifests/` directory without duplicating files.

## Non-Obvious Details

**Application Grouping Mirrors Compose Profiles**: The two Application resources (core-services, data-pipeline) correspond to Docker Compose profiles, maintaining deployment consistency between Docker and Kubernetes environments. Same logical service groupings work across both orchestrators.

**IgnoreDifferences for Replicas**: Both Applications ignore drift on `spec.replicas` fields for Deployments and StatefulSets. This allows horizontal pod autoscaling or manual replica adjustments without triggering OutOfSync status.

**Finalizers Ensure Clean Deletion**: Applications include `resources-finalizer.argocd.argoproj.io` finalizer, ensuring ArgoCD deletes all managed resources before removing the Application resource itself. Prevents orphaned resources.

**Retry with Exponential Backoff**: Sync failures retry up to 5 times with exponential backoff (5s initial, 2x factor, 3m max). Handles transient issues like image pull delays or dependency startup timing.

**PruneLast Ordering**: Applications use `PruneLast=true` sync option, ensuring resource deletions happen after updates. Prevents downtime from deleting a service before its replacement is ready.

**Install Manifest is Upstream**: The `install.yaml` is ArgoCD's official installation manifest (v2.12.3), not a custom configuration. It's committed for version pinning and offline installation, not hand-written.

## Related Modules

- **[infrastructure/kubernetes](../CONTEXT.md)** — Provides the Kubernetes manifests that ArgoCD monitors and syncs; ArgoCD implements the GitOps pattern for deploying these resources
- **[infrastructure/docker](../../docker/CONTEXT.md)** — Alternative orchestration environment; ArgoCD application groupings mirror Docker Compose profile structure
