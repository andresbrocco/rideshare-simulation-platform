# CONTEXT.md — Manifests

## Purpose

Raw Kubernetes manifests for deploying the full rideshare simulation platform to a local cluster. These manifests are applied directly (or via Kustomize overlays) and cover all application services, infrastructure dependencies, networking, storage, and secret management.

## Responsibility Boundaries

- **Owns**: All base Kubernetes resource definitions — Deployments, Services, ConfigMaps, Secrets, PersistentVolumes, PersistentVolumeClaims, CronJobs, HTTPRoutes, GatewayClass, StorageClass, and External Secrets CRDs
- **Delegates to**: Kustomize overlays (`infrastructure/kubernetes/overlays/`) for environment-specific patching (image tags, replica counts, resource limits)
- **Does not handle**: Helm chart templating, ArgoCD Application definitions, Terraform-managed cloud resources, or cluster bootstrapping (those live in `infrastructure/kubernetes/argocd/` and `infrastructure/terraform/`)

## Key Concepts

**Gateway API routing**: Ingress is not used. The platform uses `GatewayClass` (named `eg`, backed by Envoy Gateway) and `HTTPRoute` resources. All path-based routing strips the path prefix before forwarding — e.g., `/api/` rewrites to `/` before hitting the simulation service. Two HTTPRoute files split responsibilities: `httproute-api.yaml` handles the simulation API and frontend root, `httproute-web-services.yaml` handles Airflow, Grafana, Prometheus, and Trino UIs.

**External Secrets integration**: `external-secrets-secretstore.yaml` defines a `SecretStore` pointing to AWS Secrets Manager. In local development the ESO controller is configured with `AWS_ENDPOINT_URL=http://localstack:4566`, so it transparently hits LocalStack instead of real AWS. The ExternalSecret CRDs (`external-secrets-api-keys.yaml`, `external-secrets-app-credentials.yaml`) are identical for local and production — only the controller endpoint changes. Switching to real AWS requires removing the endpoint override from the ESO Helm install, not changing these manifests.

**Static PersistentVolumes with node affinity**: Local storage uses `hostPath` PVs defined in `pv-static.yaml` with explicit `nodeAffinity` pinning volumes to specific nodes (`rideshare-local-worker`, `rideshare-local-worker2`). The StorageClass (`storageclass.yaml`) uses `rancher.io/local-path` provisioner with `volumeBindingMode: Immediate`. This is a local-only pattern; cloud overlays use dynamically provisioned PVCs instead.

**Dependency-ordered startup via initContainers**: `simulation.yaml` uses five sequential initContainers (Kafka, Schema Registry, Redis, OSRM, Stream Processor) to enforce startup ordering within the cluster. Each polls its dependency's health endpoint before proceeding. This replaces Docker Compose `depends_on` semantics in Kubernetes where native ordering is not available.

**bronze-init as a CronJob**: `bronze-init.yaml` is a CronJob (runs every 10 minutes) rather than a one-shot Job. It registers Delta table locations in Hive Metastore via Trino using `CALL delta.system.register_table(...)`. The registration is idempotent — tables already registered are skipped. Running continuously handles the case where data arrives in S3 after the initial cluster start. The registration script is embedded as a ConfigMap shell script and executed inside a `trinodb/trino` container image.

## Non-Obvious Details

- The `secret-credentials.yaml` and `secret-api-keys.yaml` files contain development-default credentials. In production these Kubernetes Secrets are replaced by ExternalSecret-synced secrets — the `secret-*.yaml` files are only applied in local environments where LocalStack is not yet bootstrapped or for initial cluster setup.
- OSRM's liveness and readiness probes use a hardcoded São Paulo coordinate pair (`-46.6333,-23.5505`) as the health check URL. The `initialDelaySeconds` is very high (180–300s) because OSRM must load pre-processed road network data on startup.
- `configmap-core.yaml` centralizes shared env vars but individual service manifests override specific values inline (e.g., simulation overrides `SIM_SPEED_MULTIPLIER` directly in its pod spec). The ConfigMap is not always consumed via `envFrom`; services reference individual keys.
- `bronze-init.yaml` stores its entire registration shell script inside a ConfigMap and mounts it at `/opt/init-scripts/` — there is no separate application image for this job; it uses the stock `trinodb/trino:451` image with the `trino` CLI.
- The `external-secrets-namespace.yaml` and `external-secrets-aws-credentials.yaml` must be applied to the `external-secrets` namespace (not `default`) — this is the namespace where the ESO controller looks for provider credentials.

## Related Modules

- [infrastructure/kubernetes/argocd](../argocd/CONTEXT.md) — Dependency — ArgoCD GitOps configuration for deploying the rideshare platform to production K...
- [infrastructure/kubernetes/components](../components/CONTEXT.md) — Reverse dependency — Provides aws-production component (kustomization.yaml)
- [infrastructure/kubernetes/components/aws-production](../components/aws-production/CONTEXT.md) — Reverse dependency — Provides ECR image references for all custom services, ServiceAccounts for IRSA/Pod Identity workloads, SecretStore aws-secrets-manager (+4 more)
- [infrastructure/kubernetes/overlays](../overlays/CONTEXT.md) — Dependency — Mutually exclusive Kustomize overlays that produce complete production deploymen...
- [infrastructure/kubernetes/overlays](../overlays/CONTEXT.md) — Reverse dependency — Provides production-duckdb/kustomization.yaml, production-glue/kustomization.yaml
- [infrastructure/kubernetes/overlays/production-duckdb](../overlays/production-duckdb/CONTEXT.md) — Reverse dependency — Consumed by this module
- [infrastructure/kubernetes/overlays/production-glue](../overlays/production-glue/CONTEXT.md) — Reverse dependency — Consumed by this module
- [infrastructure/kubernetes/scripts](../scripts/CONTEXT.md) — Reverse dependency — Provides create-cluster.sh, deploy-services.sh, health-check.sh (+2 more)
- [infrastructure/kubernetes/tests](../tests/CONTEXT.md) — Reverse dependency — Consumed by this module
