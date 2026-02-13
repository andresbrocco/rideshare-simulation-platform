# CONTEXT.md — Infrastructure

## Purpose

Provides the deployment and orchestration layer for the rideshare simulation platform across multiple environments (local Docker, Kubernetes, cloud). Implements centralized secrets management, profile-based deployment strategies, and infrastructure-as-code patterns for consistent deployment from development to production.

## Responsibility Boundaries

- **Owns**: Deployment orchestration (Docker Compose, Kubernetes manifests), secrets management infrastructure, environment-specific configuration, infrastructure provisioning scripts, deployment lifecycle automation
- **Delegates to**: Service application logic (implemented in `services/`), container image building (Dockerfiles in service directories), cloud resource provisioning (Terraform modules, currently placeholder)
- **Does not handle**: Application code, business logic, data transformations, API implementation

## Key Concepts

**Profile-Based Deployment**: Services are organized into logical groups (core, data-pipeline, monitoring, spark-testing) that can be deployed independently or combined. Pattern is consistent across both Docker Compose and Kubernetes, allowing selective resource allocation based on use case.

**Centralized Secrets Management**: All credentials stored in AWS Secrets Manager (LocalStack for development, real AWS for production). The `secrets-init` service fetches secrets and writes grouped env files for each profile, ensuring no credentials are hardcoded in compose files or manifests. Changing `AWS_ENDPOINT_URL` from LocalStack to AWS is the only migration step required.

**Multi-Environment Strategy**: Same codebase deploys to Docker Compose (local development), Kubernetes with Kind (cloud parity testing), and cloud environments (AWS via Terraform modules). Environment differences handled through overlays (Kustomize) and environment variables rather than separate codebases.

**Secrets Grouping**: Secrets are fetched from Secrets Manager and written to profile-specific env files (`/secrets/core.env`, `/secrets/data-pipeline.env`, `/secrets/monitoring.env`) to minimize credential exposure. Each profile only receives credentials for its services.

**Bootstrap Scripts**: Utility scripts in `scripts/` directory handle infrastructure initialization tasks independent of service containers (secret seeding, Bronze table validation, DBT export to S3). These run in CI/CD pipelines and one-shot initialization containers.

## Non-Obvious Details

**LocalStack Migration Path**: The entire secrets infrastructure works with both LocalStack (local) and AWS Secrets Manager (production) without code changes. Only the `AWS_ENDPOINT_URL` environment variable determines the target. This allows seamless promotion from local development to cloud deployment.

**Key Transformation Logic**: The `fetch-secrets.py` script applies transformations to avoid environment variable name collisions when multiple secrets share a profile. For example, `rideshare/postgres-airflow` and `rideshare/postgres-metastore` both have `POSTGRES_USER` keys, which get transformed to `POSTGRES_AIRFLOW_USER` and `POSTGRES_METASTORE_USER`.

**Airflow Secret Flattening**: Airflow secrets use double-underscore notation (`AIRFLOW__CORE__FERNET_KEY`) to match Airflow's configuration hierarchy, while other secrets use simple key names. This transformation happens transparently in `fetch-secrets.py`.

**Docker vs Kubernetes Parity**: Both orchestration systems use identical container images and environment variables, but differ in networking (Docker uses single bridge network with internal DNS, Kubernetes uses Gateway API for ingress) and storage (Docker uses named volumes, Kubernetes uses PersistentVolumes).

**Terraform Module Placeholders**: The `terraform/` directory contains `.gitkeep` files for future cloud provisioning modules (ECS, MSK, ElastiCache, Databricks). Current production deployment strategy uses Docker Compose or Kubernetes; Terraform modules are roadmap items.

**DBT Export Bridge**: The `export-dbt-to-s3.py` script bridges DuckDB-based local transformations to S3 Delta tables for Trino querying in Grafana dashboards. This allows local development with DuckDB while maintaining production parity with Spark/Trino.

## Related Modules

- **[infrastructure/docker](docker/CONTEXT.md)** — Primary deployment orchestration for local development; implements the profile-based deployment strategy with Docker Compose service definitions
- **[infrastructure/kubernetes](kubernetes/CONTEXT.md)** — Kubernetes deployment alternative using same profile organization and secrets management patterns for cloud parity testing
- **[infrastructure/scripts](scripts/CONTEXT.md)** — Contains bootstrap and operational scripts that implement the secrets management and data pipeline validation logic referenced in deployment workflows
