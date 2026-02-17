# CONTEXT.md — Infrastructure

## Purpose

Provides the deployment, orchestration, and cloud provisioning layer for the rideshare simulation platform. Covers Docker Compose for local development, Kubernetes (Kind and EKS) for container orchestration, Terraform for AWS infrastructure-as-code, and operational scripts for secrets management and data pipeline utilities.

## Responsibility Boundaries

- **Owns**: Docker Compose multi-profile deployment, Kubernetes manifests and overlays, Terraform cloud provisioning (bootstrap → foundation → platform), secrets management infrastructure, ArgoCD GitOps configuration, Kustomize environment overlays
- **Delegates to**: Service application logic and Dockerfiles (`services/`), data transformations (`tools/dbt/`), CI/CD workflow definitions (`.github/workflows/`)
- **Does not handle**: Application code, business logic, container image building, LDAP authentication setup (`services/openldap/`)

## Key Concepts

**Three-Layer Terraform Architecture** — Cloud infrastructure is provisioned in three dependent layers: (1) Bootstrap creates the S3 state bucket and DynamoDB lock table, (2) Foundation provisions VPC, Route 53, ACM, S3 data buckets, CloudFront, ECR, Secrets Manager, and IAM roles (8 modules), (3) Platform provisions EKS, RDS, ALB controller, and DNS records (4 modules). Each layer stores state in the bootstrap bucket and platform reads foundation outputs via `terraform_remote_state`.

**Profile-Based Deployment** — Services are organized into logical groups (core, data-pipeline, monitoring, spark-testing) that can be deployed independently or combined. Pattern is consistent across both Docker Compose and Kubernetes, allowing selective resource allocation based on use case.

**Centralized Secrets Management** — All credentials stored in AWS Secrets Manager (LocalStack for development, real AWS for production). The `secrets-init` service fetches secrets and writes grouped env files (`/secrets/core.env`, `/secrets/data-pipeline.env`, `/secrets/monitoring.env`) for each profile. Changing `AWS_ENDPOINT_URL` from LocalStack to AWS is the only migration step required.

**Multi-Environment Strategy** — Same codebase deploys to Docker Compose (local development), Kubernetes with Kind (cloud parity testing), and EKS (production). Environment differences handled through Kustomize overlays and environment variables rather than separate codebases.

**GitOps with ArgoCD** — Production Kubernetes deployments use ArgoCD for declarative GitOps. ArgoCD watches the repository and applies Kustomize overlays to sync cluster state with the repository.

**Kustomize Overlays** — Local (Kind) and production (EKS) overlays customize base manifests for each environment. Local overlays adjust resource limits for the Kind budget (10GB total), while production overlays configure ingress, persistent storage, and external DNS.

## Non-Obvious Details

**Foundation → Platform Remote State Dependency** — Platform layer reads foundation outputs (subnet IDs, security group IDs, IAM role ARNs) via `data "terraform_remote_state"`. This means foundation must be applied before platform, and changes to foundation outputs require platform re-apply.

**Environments/ tfvars as Canonical Variable Source** — Production variable values live in `terraform/environments/prod/foundation.tfvars` and `platform.tfvars`. The `variables.tf` defaults match prod values, so `terraform plan` works without `-var-file`, but the environments/ files are the documented source of truth.

**Key Transformation Logic** — The `fetch-secrets.py` script applies transformations to avoid environment variable name collisions when multiple secrets share a profile. For example, `rideshare/postgres-airflow` and `rideshare/postgres-metastore` both have `POSTGRES_USER` keys, which get transformed to `POSTGRES_AIRFLOW_USER` and `POSTGRES_METASTORE_USER`.

**Docker vs Kubernetes Networking/Storage Parity** — Both orchestration systems use identical container images and environment variables, but differ in networking (Docker uses single bridge network with internal DNS, Kubernetes uses Gateway API for ingress) and storage (Docker uses named volumes, Kubernetes uses PersistentVolumes).

**Kind Resource Budget** — The local Kind cluster is configured with a 10GB total memory budget. Kustomize local overlays reduce resource requests/limits to fit within this constraint.

**DBT Export Bridge** — The `export-dbt-to-s3.py` script bridges DuckDB-based local transformations to S3 Delta tables for Trino querying in Grafana dashboards. This allows local development with DuckDB while maintaining production parity with Spark/Trino.

## Related Modules

- **[infrastructure/docker](docker/CONTEXT.md)** — Docker Compose multi-profile orchestration for local development
- **[infrastructure/docker/dockerfiles](docker/dockerfiles/CONTEXT.md)** — Custom Dockerfiles for services requiring build-time configuration
- **[infrastructure/kubernetes](kubernetes/CONTEXT.md)** — Kubernetes deployment with Kind (local) and EKS (production)
- **[infrastructure/kubernetes/manifests](kubernetes/manifests/CONTEXT.md)** — Base Kubernetes manifests for all services
- **[infrastructure/kubernetes/overlays](kubernetes/overlays/CONTEXT.md)** — Kustomize overlays for local vs production environments
- **[infrastructure/kubernetes/argocd](kubernetes/argocd/CONTEXT.md)** — ArgoCD GitOps configuration for production deployments
- **[infrastructure/kubernetes/scripts](kubernetes/scripts/CONTEXT.md)** — Kubernetes cluster management scripts
- **[infrastructure/scripts](scripts/CONTEXT.md)** — Secrets management, data pipeline, and infrastructure automation scripts
