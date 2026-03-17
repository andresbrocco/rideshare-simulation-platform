# CONTEXT.md — Workflows

## Purpose

Defines the full CI/CD lifecycle for the rideshare simulation platform: static quality gates on every push, selective Docker image builds to ECR, full EKS platform provisioning, GitOps-driven Kubernetes deployment via ArgoCD, cost-driven teardown, and a soft-reset that wipes all runtime state while preserving infrastructure.

## Responsibility Boundaries

- **Owns**: CI gate logic, ECR image tagging strategy, Kubernetes deploy sequencing, Route 53 DNS management, platform teardown ordering, soft-reset data wipe procedure
- **Delegates to**: Terraform (infrastructure provisioning), ArgoCD (Kubernetes reconciliation), Lambda `rideshare-auth-deploy` (visitor session management and deploy progress reporting)
- **Does not handle**: Application logic, Terraform module definitions, Kubernetes manifest content (those live in `infrastructure/`)

## Key Concepts

**Foundation vs. Platform split**: Infrastructure is split into two Terraform layers. The `deploy-platform` workflow verifies that `foundation` has no unapplied changes before touching `platform`. Foundation resources (S3 buckets, ECR repos, CloudFront, secrets) persist across teardowns; platform resources (EKS, RDS, ALB) are ephemeral and destroyed to eliminate cost between demos.

**`deploy` branch as materialized artifact**: The `deploy-platform` workflow resolves runtime placeholders (`<account-id>`, `<acm-cert-arn>`, `<rds-endpoint>`, `<image-tag>`, `<alb-sg-id>`) directly into Kubernetes YAML files, then force-pushes those resolved files to the `deploy` branch with `[skip ci]`. ArgoCD watches the `deploy` branch with `selfHeal: true`, so that branch must never contain unresolved placeholders. The `main` branch always retains placeholder tokens.

**State reconciliation before apply**: The deploy workflow runs `terraform import` for every known EKS resource (cluster, node group, addons, Helm releases) before planning. This handles orphaned state from previous partial applies without requiring manual intervention.

**Phased convergence reporting**: The "Wait for EKS convergence" step waits for services in dependency order across five phases (infrastructure → schema → application → data-pipeline → UI) and reports each service's readiness to the Lambda function. A marker-file pattern (`wait_and_mark` / `report_phase`) avoids read-modify-write races when multiple services are waited in parallel.

**OSRM data sourcing**: The `build-images` workflow sources the Sao Paulo OSM `.pbf` file from an S3 build-assets bucket first (fast cache hit), falling back to Git LFS on miss and then uploading to S3 for future builds. A size check guards against accidentally bundling an LFS pointer file.

**Reset platform vs. teardown**: `teardown-platform` destroys EKS, RDS, and ALB but preserves S3 data and ECR images. `reset-platform` keeps all infrastructure intact but wipes all runtime state: Kafka (PVC delete+recreate), S3 lakehouse buckets, RDS databases (drop+recreate), Redis (FLUSHALL), and monitoring emptyDir volumes. The reset temporarily suspends ArgoCD auto-sync to prevent it from fighting the scale-down operations, then restores it at the end.

**DBT runner selection**: Both the deploy and soft-reset workflows accept a `dbt_runner` input (`duckdb` or `glue`). This controls which Kustomize overlay is applied and whether Glue Catalog tables or Hive Metastore databases are managed. The `glue` path also manages Glue database table deletion during soft-reset.

## Non-Obvious Details

- The `build-images` workflow uses a dynamic matrix generated from path-filter outputs; `simulation` and `control-panel` always receive a `"target": "production"` build-arg because those images have multi-stage Dockerfiles where the production stage bakes in VITE environment variables. Other services have no `target` field and use the default (final) stage.
- The simulation service's Docker build context does not include `schemas/` by default (it lives at repo root), so the CI step temporarily copies `schemas/` into `services/simulation/schemas` before the build and removes it after.
- Credentials for the integration test run are loaded by parsing LocalStack Secrets Manager responses, applying key-rename mappings for Airflow (e.g., `FERNET_KEY` → `AIRFLOW__CORE__FERNET_KEY`) and Grafana before exporting them into `GITHUB_ENV`. This mirrors the logic in `infrastructure/scripts/fetch-secrets.py`.
- The `teardown-platform` workflow attempts a graceful simulation pause (entering DRAINING state) before destroying infrastructure. It speeds the simulation to 16× and enables the PID controller to drain active trips faster, then polls for up to 5 minutes before proceeding regardless.
- RDS database reset in soft-reset uses `kubectl run` to spin up ephemeral `postgres:16` pods because the GitHub Actions runner has no network path to RDS directly; all DB operations are proxied through the EKS cluster.
- The deploy workflow installs Lambda dependencies with `--platform manylinux2014_x86_64 --only-binary=:all:` to produce a Linux-compatible package on the macOS/ubuntu runner before bundling and deploying the Lambda function.
- The `deploy-lambda-auth` and `deploy-lambda-chat` workflows each have a comment acknowledging that `update-function-code` causes Terraform to detect source-hash drift on the next `plan`. This is accepted as a no-op on the next apply if no source changes occurred.
