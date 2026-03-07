# CONTEXT.md — Kubernetes

## Purpose

Kubernetes deployment configuration for the rideshare platform, supporting both a local Kind cluster (development) and AWS EKS (production). Defines all workload manifests, Kustomize overlays for environment differentiation, ArgoCD GitOps automation, and External Secrets Operator integration for secret management.

## Responsibility Boundaries

- **Owns**: All Kubernetes manifests, Kustomize overlay structure, ArgoCD Application spec, cluster bootstrap scripts, and Kubernetes-level secret wiring
- **Delegates to**: `infrastructure/terraform/` for cloud resource provisioning (EKS cluster, RDS, S3, IAM roles); service source directories for container image contents
- **Does not handle**: Container image builds, application-level configuration logic, or Terraform state

## Key Concepts

**Kustomize overlay pattern**: `manifests/` is the shared base — raw YAML files for every workload. Two production overlays consume this base:
- `overlays/production-duckdb/` — includes Hive Metastore + RDS PostgreSQL metastore; Trino uses a local thrift URI
- `overlays/production-glue/` — omits Hive Metastore entirely; Trino uses AWS Glue Data Catalog

Both overlays apply `components/aws-production/` which patches all manifests for EKS: swap storage classes to EBS, add ingress resources, patch ConfigMaps with production endpoints, and configure IRSA/Pod Identity service accounts. Switching the active runner means changing the ArgoCD Application `path` field to point at the desired overlay.

**ArgoCD watches the `deploy` branch**, not `main`. `selfHeal: true` means any out-of-band `kubectl` changes are automatically reverted within the 3-minute reconciliation interval. Replica count drift is explicitly ignored via `ignoreDifferences` to allow manual scaling without revert.

**External Secrets Operator (ESO)** bridges secret stores to Kubernetes Secrets. In development (Kind), ESO is pointed at a LocalStack endpoint via `AWS_ENDPOINT_URL` set on the ESO controller helm values — the `SecretStore` YAML itself is identical between dev and prod; only the ESO controller's endpoint env var differs. In production, the LocalStack endpoint env var is removed and ESO uses node role credentials to reach real AWS Secrets Manager.

**bronze-init CronJob** runs every 10 minutes and calls `CALL delta.system.register_table(...)` via Trino CLI to register Bronze Delta tables. It is idempotent and tolerant of missing data (tables without S3 objects are skipped as warnings). This is needed because Delta tables written by bronze-ingestion don't auto-register in Hive Metastore or Glue.

**Static PVs for local Kind**: `pv-static.yaml` binds hostPath volumes to specific Kind worker nodes (`rideshare-local-worker`, `rideshare-local-worker2`) using `nodeAffinity`. These are not used in production (EBS StorageClass is applied by the `aws-production` component instead).

## Non-Obvious Details

- The ArgoCD Application YAML in `argocd/app-rideshare-platform.yaml` contains a literal placeholder `overlays/production-<dbt-runner>` — it must be edited before applying to set either `production-duckdb` or `production-glue` as the path.
- Simulation's `simulation.db` is mounted as an `emptyDir`, so the SQLite checkpoint is lost on pod restart. Persistence for the sim database is not provided in any manifest.
- The `deploy-services.sh` script applies manifests imperatively (no Kustomize); it is the local Kind deployment path. ArgoCD is the production deployment path. These two paths are not reconciled — changes to manifests must be propagated to both if local Kind usage is needed.
- StorageClass application uses `set +e` / grep filtering for the "field is immutable" error because Kind ships a default `standard` StorageClass that conflicts with the manifest on re-apply.
- The `aws-production` component patches replicas to `ignoreDifferences` for Deployments and StatefulSets, but ArgoCD's automated prune will still remove resources deleted from Git.
- Kafka headless service DNS (`kafka-0.kafka:29092`) is hardcoded across multiple init containers and env vars rather than read from ConfigMap.

## Related Modules

- [services](../../services/CONTEXT.md) — Reverse dependency — Consumed by this module
- [services/airflow](../../services/airflow/CONTEXT.md) — Reverse dependency — Provides dbt_silver_transformation (DAG), dbt_gold_transformation (DAG), delta_maintenance (DAG) (+1 more)
