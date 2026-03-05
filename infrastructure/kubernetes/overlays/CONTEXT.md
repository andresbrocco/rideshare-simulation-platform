# CONTEXT.md — Kubernetes Overlays

## Purpose

Environment-specific Kustomize overlays that produce self-contained, deployable production targets. Each overlay references base manifests directly and pulls shared AWS configuration from a Kustomize Component (`components/aws-production/`).

## Responsibility Boundaries

- **Owns**: Variant-specific configuration (Hive Metastore for duckdb, Glue catalog for glue), namespace assignment, variant-specific image overrides and patches
- **Delegates to**: Shared AWS production config (ECR images, IRSA, ExternalSecrets, ALB Ingress, monitoring patches) in `components/aws-production/`, base manifests in `manifests/`
- **Does not handle**: Individual service deployment manifests (those live in manifests/) or cluster provisioning (handled by Terraform)

## Key Concepts

- **Kustomize Component Pattern**: Shared AWS production configuration lives in `components/aws-production/` as a `kind: Component` (`v1alpha1`). Both overlays include it via the `components:` field, avoiding duplication while keeping each overlay self-contained.
- **production-duckdb Overlay**: Deploys Hive Metastore backed by RDS PostgreSQL for Trino catalog resolution. Used when `DBT_RUNNER=duckdb`.
- **production-glue Overlay**: Uses AWS Glue Data Catalog for Trino; no Hive Metastore pod or metastore database. Used when `DBT_RUNNER=glue`.

## Non-Obvious Details

Every directory under `overlays/` is a directly buildable target (`kustomize build`). There is no shared "production base" overlay — that role is filled by the Component. Switching between runners requires changing only the ArgoCD Application `path` field.
