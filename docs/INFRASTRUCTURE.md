# INFRASTRUCTURE.md

> Operations and infrastructure facts for this codebase.

## CI/CD

### Platform

GitHub Actions. Eight workflow files in `.github/workflows/`.

### Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | push/PR to `main` | Lint, type-check, unit tests, frontend build, API contract validation |
| `build-images.yml` | push to `main` (path-filtered), `workflow_dispatch` | Build and push Docker images to ECR per changed service; OSRM `.pbf` sourced from S3 build-assets (fallback to Git LFS) |
| `deploy.yml` | `workflow_dispatch` | Provision EKS platform via Terraform, push `deploy` branch, install ArgoCD, wait for phased convergence (5 phases, 15 services), report readiness to Lambda |
| `teardown-platform.yml` | `workflow_dispatch` | Graceful simulation shutdown (drain to 16× speed, poll up to 5 min), delete Route 53 record, `terraform destroy` on platform layer |
| `soft-reset.yml` | `workflow_dispatch` | Wipe Kafka, S3 lakehouse, RDS databases, Redis, monitoring data — suspends ArgoCD auto-sync during reset, then restores; keeps EKS cluster intact |
| `deploy-lambda.yml` | push to `main` (`services/auth-deploy/**`, `services/ai-chat/**`), `workflow_dispatch` | Package and deploy `rideshare-auth-deploy` Lambda function code (Linux-compatible wheels via `--platform manylinux2014_x86_64`) |
| `integration-tests.yml` | `schedule` (weekly Monday 02:00 UTC), `workflow_dispatch` | Spin up Docker Compose, run `tests/integration/`, upload results |
| `visitor-login.yml` | `workflow_dispatch` | Visitor authentication workflow for pre-deploy Lambda validation |

### CI Pipeline Steps (`ci.yml`)

1. Set up Python 3.13, Node.js 20, Terraform 1.14.3, TFLint
2. Create per-service virtualenvs; install all Python dev dependencies
3. Install frontend dependencies (`npm ci`)
4. Run `pre-commit --all-files` (ruff, mypy, black, TFLint, Terraform format)
5. Run simulation unit tests (`pytest`)
6. Run stream-processor unit tests (`pytest`)
7. Build frontend (`npm run build`)
8. On API path changes: export OpenAPI spec, validate spec, generate TypeScript types, validate type parity

### Deploy Phased Convergence

The `deploy.yml` "Wait for EKS convergence" step waits for services in dependency order across five phases:

| Phase | Services |
|-------|---------|
| 1 — Infrastructure | secrets, kafka, redis, osrm |
| 2 — Schema | schema-registry, hive-metastore, postgres |
| 3 — Application | simulation, stream-processor, bronze-ingestion, trino |
| 4 — Data Pipeline | airflow |
| 5 — UI | control-panel, grafana, prometheus |

Each service's readiness is reported to the Lambda function via `report-deploy-progress`. A marker-file pattern (`wait_and_mark` / `report_phase`) prevents read-modify-write races when multiple services are waited in parallel. `all_ready` becomes true when all 15 services have `ready: true`.

### Authentication to AWS

GitHub Actions assumes `rideshare-github-actions` IAM role via OIDC web identity federation. The trust policy is restricted to the `main` branch. No long-lived AWS credentials are stored as GitHub secrets.

### Terraform Version

1.14.3 (pinned via `hashicorp/setup-terraform@v3`).

---

## Containerization

### Docker

All services have Dockerfiles under their respective `services/<name>/` directories. No root-level Dockerfile.

| Service | Build Context | Notes |
|---------|--------------|-------|
| `simulation` | `services/simulation/` | `schemas/` directory copied into build context before build; removed after |
| `stream-processor` | `services/stream-processor/` | Standard Python image |
| `control-panel` | `services/control-panel/` | Multi-stage build; production URLs baked in as `VITE_*` build args |
| `bronze-ingestion` | `services/bronze-ingestion/` | Standard Python image |
| `hive-metastore` | `services/hive-metastore/` | Custom Hive 4.0 build |
| `osrm` | `services/osrm/` | Custom OSRM build with Sao Paulo road network data |
| `otel-collector` | `services/otel-collector/` | OTel contrib image; adds `wget` via BusyBox for health checks |
| `performance-controller` | `services/performance-controller/` | Standard Python image |

Images are pushed to Amazon ECR with two tags: `<git-sha>` and `latest`. Registry path pattern: `<account>.dkr.ecr.us-east-1.amazonaws.com/rideshare/<service>`.

Layer cache is stored in ECR using `type=registry,mode=max` cache.

### Docker Compose

File: `infrastructure/docker/compose.yml`

Four named profiles partition the stack:

| Profile | Services |
|---------|----------|
| `core` | kafka, kafka-init, schema-registry, redis, osrm, simulation, stream-processor, control-panel, localstack, secrets-init |
| `data-pipeline` | minio, minio-init, bronze-ingestion, airflow-webserver, airflow-scheduler, hive-metastore, trino, delta-table-init, postgres-airflow, postgres-metastore, localstack, secrets-init |
| `monitoring` | prometheus, grafana, loki, tempo, otel-collector, cadvisor, minio, minio-init, localstack, secrets-init |
| `performance` | performance-controller, localstack, secrets-init |

`localstack` and `secrets-init` appear in all profiles. `minio` and `minio-init` appear in both `data-pipeline` and `monitoring` (Loki and Tempo use MinIO for storage backends).

### Compose Test Overlay

`compose.test.yml` adds a `test` profile with `test-data-producer` and `test-runner` services. It declares the base network as `external: true` and requires the base stack to be running.

### Notable Compose Service Behaviors

- **`lambda-init`**: In addition to deploying the auth Lambda, mounts three visitor-provisioning modules (`provision_grafana_viewer.py`, `provision_airflow_viewer.py`, `provision_minio_visitor.py`) and a MinIO policy file (`minio-visitor-readonly.json`) into the Lambda package path. Injects service endpoint environment variables (`GRAFANA_URL`, `AIRFLOW_URL`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `SIMULATION_API_URL`) so the deployed Lambda can call those services at runtime.
- **`secrets-init`**: Now installs `bcrypt` alongside `boto3` so `seed-secrets.py` can generate `$2b$10$...` hashed Trino passwords at seed time.
- **Simulation**: The entrypoint conditionally sources `/secrets/data-pipeline.env` before sourcing MinIO credentials — allows the simulation to start under `core`-only profile without MinIO.
- **Grafana**: Also conditionally sources `/secrets/data-pipeline.env` (same pattern as simulation) to access Trino connection details without requiring the `data-pipeline` profile.

### Build Command

```bash
docker compose -f infrastructure/docker/compose.yml --profile core build
```

### Run Command (full stack)

```bash
docker compose -f infrastructure/docker/compose.yml \
  --profile core \
  --profile data-pipeline \
  --profile monitoring \
  up -d
```

---

## Secrets Bootstrap

All credentials are sourced from Secrets Manager, not from static `.env` files.

### Local Development Sequence

1. `localstack` container starts (AWS emulation on port 4566)
2. `secrets-init` runs `infrastructure/scripts/seed-secrets.py` — populates four secret groups in LocalStack Secrets Manager
3. `secrets-init` then runs `infrastructure/scripts/fetch-secrets.py` — reads the groups and writes grouped `.env` files to a shared Docker volume at `/secrets/`
4. All other services mount the volume read-only and source the relevant `.env` file in their entrypoints

### Secret Groups

| Secret Name | Written To | Contains |
|------------|-----------|---------|
| `rideshare/api-key` | `/secrets/core.env` | `API_KEY` |
| `rideshare/core` | `/secrets/core.env` | `KAFKA_SASL_*`, `REDIS_PASSWORD`, `SCHEMA_REGISTRY_*` |
| `rideshare/data-pipeline` | `/secrets/data-pipeline.env` | `MINIO_ROOT_*`, `POSTGRES_*`, `AIRFLOW__*`, `FERNET_KEY` |
| `rideshare/monitoring` | `/secrets/monitoring.env` | `GF_SECURITY_ADMIN_USER`, `GF_SECURITY_ADMIN_PASSWORD` |
| `rideshare/github-pat` | (Secrets Manager only) | `GITHUB_PAT` used by Lambda |
| `rideshare/trino-admin-password-hash` | (Secrets Manager only; not Terraform-managed) | bcrypt hash of Trino `admin` password; created by deploy workflow |
| `rideshare/trino-visitor-password-hash-*` | (Secrets Manager only; not Terraform-managed) | PBKDF2 hash of each visitor's Trino password; created dynamically by auth-deploy Lambda on `provision-visitor` |

`seed-secrets.py` requires the `bcrypt` library (installed in `secrets-init` alongside `boto3`) to generate `$2b$10$...` prefixed hashes for the two Trino hash secrets at seed time.

### Production Secret Management

External Secrets Operator (ESO) syncs secrets from AWS Secrets Manager to Kubernetes Secrets. The `SecretStore` YAML is identical between dev and prod; only the ESO controller's `AWS_ENDPOINT_URL` env var changes (absent in production, points to LocalStack in dev).

---

## Configuration Management

### Environment Variables

Source: `/secrets/*.env` files (mounted from `secrets-init` volume) in Docker; AWS Secrets Manager via ESO in Kubernetes. No credentials in `.env` files committed to the repository.

### Example File

`.env.example` at the repository root documents the configuration surface for local non-Docker development.

### Key Variables

| Variable | Service | Purpose | Default |
|----------|---------|---------|---------|
| `SIM_SPEED_MULTIPLIER` | simulation | Simulated-to-real time ratio | `1` |
| `SIM_LOG_LEVEL` | simulation | Logging verbosity | `INFO` |
| `SIM_CHECKPOINT_INTERVAL` | simulation | Checkpoint cadence (sim seconds) | `300` |
| `KAFKA_BOOTSTRAP_SERVERS` | simulation, stream-processor, bronze-ingestion | Kafka broker address | set by secrets-init |
| `KAFKA_SASL_USERNAME` / `KAFKA_SASL_PASSWORD` | simulation, stream-processor, bronze-ingestion | Kafka SASL/PLAIN auth | set by secrets-init |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | simulation, stream-processor | Redis connection | set by secrets-init |
| `OSRM_BASE_URL` | simulation | OSRM routing endpoint | `http://localhost:5000` |
| `PROCESSOR_WINDOW_SIZE_MS` | stream-processor | GPS aggregation window | `100` |
| `PROCESSOR_AGGREGATION_STRATEGY` | stream-processor | `latest` or `sample` | `latest` |
| `VITE_API_URL` | control-panel | REST API base URL | `http://localhost:8000` |
| `VITE_WS_URL` | control-panel | WebSocket URL | `ws://localhost:8000/ws` |
| `VITE_LAMBDA_URL` | control-panel | Lambda function URL for deploy/teardown | baked at build time |
| `AWS_REGION` | all | AWS region | `us-east-1` |
| `CORS_ORIGINS` | simulation | Allowed CORS origins | `http://localhost:5173,...` |
| `GRAFANA_URL` | lambda (runtime) | Grafana API endpoint for visitor provisioning | injected by lambda-init |
| `AIRFLOW_URL` | lambda (runtime) | Airflow API endpoint for visitor provisioning | injected by lambda-init |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` | lambda (runtime) | MinIO connection for visitor provisioning | injected by lambda-init |
| `SIMULATION_API_URL` | lambda (runtime) | Simulation API base URL for visitor account registration | injected by lambda-init |
| `POSTGRES_AIRFLOW_USER` / `POSTGRES_AIRFLOW_PASSWORD` | grafana | Credentials for `airflow-postgres` datasource (visitor activity dashboard) | set by secrets-init |

### Override Mechanism

`seed-secrets.py` supports `OVERRIDE_<KEY>` environment variables. CI can inject production values at seed time without editing the script defaults.

---

## Logging and Monitoring

### Logging

- **Library**: Python `logging` module with a custom structured handler
- **Format**: JSON in production, human-readable dev format locally (controlled per service)
- **PII masking**: A log filter redacts email addresses (`[EMAIL]`) and phone numbers (`[PHONE]`) before emission — applies to all simulation service logs
- **Thread-local context**: `log_context()` context manager injects structured fields (e.g., `driver_id`, `trip_id`) into all log records emitted within its scope
- **HTTP access logging**: `RequestLoggerMiddleware` in the simulation API emits a structured access log entry for every request under logger name `api.access`, including `method`, `path`, `status_code`, `duration_ms`, `user_identity`, and `user_role`. Health check paths (`/health`, `/health/detailed`) are excluded. Identity is resolved by mapping the `X-API-Key` header to email/role via Redis session lookup (for `sess_*` keys) or to `"admin"` for the static key.
- **Shipping**: Docker container stdout/stderr is collected by the OTel Collector filelog receiver reading `/var/lib/docker/containers/*/*.log`; forwarded to Loki

### Metrics

- **Collection**: Prometheus (pull model for infrastructure exporters; push via OTel Collector remote_write for application services)
- **Application instrumentation**: OpenTelemetry SDK with OTLP/gRPC export to OTel Collector (port varies per service)
- **Infrastructure exporters**: cAdvisor (container CPU/memory, scraped at 4s interval), kafka-exporter, redis-exporter
- **Recording rules**: `services/prometheus/rules/performance.yml` — composite headroom score (`rideshare:infrastructure:headroom`) aggregated from 6 components; 4s raw and 16s smoothed variants

### Distributed Tracing

- **Backend**: Grafana Tempo
- **Protocol**: OTLP/gRPC from OTel Collector to Tempo
- **Auto-instrumentation**: FastAPI, Redis, httpx via OpenTelemetry auto-instrumentation packages
- **Cross-signal linking**: Tempo configured with `tracesToLogsV2` (Loki) and `tracesToMetrics` (Prometheus) for drill-down

### OTel Collector

Version `0.96.0`. Three independent pipelines:

| Pipeline | Receivers | Exporters |
|----------|-----------|-----------|
| Metrics | OTLP/gRPC | Prometheus remote_write |
| Logs | filelog (Docker container logs) | Loki |
| Traces | OTLP/gRPC | Tempo |

Memory limiter (180 MiB limit, 50 MiB spike) is the first processor in every pipeline.

### Grafana

Port `3001` (host). Default credentials: `admin`/`admin` (local dev).

Six dashboard folders:

| Folder | Datasource(s) | Focus |
|--------|--------------|-------|
| Monitoring | Prometheus | Simulation engine health, Kafka lag, Redis latency |
| Data Engineering | Trino + Prometheus | Bronze ingestion pipeline, Silver DAG health |
| Business Intelligence | Trino | Gold star schema analytics (driver KPIs, revenue, demand) |
| Operations | Prometheus + Trino | Unified live and historical platform state |
| Performance | Prometheus / cAdvisor | USE-method saturation and bottleneck analysis |
| Admin | airflow-postgres + Loki | Operator-only visitor activity auditing (per-service last-access timestamps) |

Five provisioned datasources:

| UID | Type | Purpose |
|-----|------|---------|
| `prometheus` | Prometheus | Metrics collection |
| `trino` | `trino-datasource` plugin | Delta Lake SQL analytics (catalog: `delta`, port 8080) |
| `loki` | Loki | Log aggregation |
| `tempo` | Tempo | Distributed traces; cross-links to Loki and Prometheus |
| `airflow-postgres` | PostgreSQL | Airflow metadata DB — used by Admin visitor-activity dashboard; requires `POSTGRES_AIRFLOW_USER`/`POSTGRES_AIRFLOW_PASSWORD` env vars |

Datasource UIDs are hardcoded in all dashboard JSON (`"uid": "prometheus"`, `"uid": "trino"`, etc.) — never use template variables (`${DS_*}`). All Trino panels must set `"rawQuery": true`, use `"rawSQL"` (capital SQL) for the query field, and `"format": 0` (table) for numeric format.

Plugin installed: `trino-datasource` (communicates via Trino HTTP REST API on port 8080 in-container).

### Health Endpoints

| Service | Endpoint | Notes |
|---------|---------|-------|
| Simulation | `GET /health` | HTTP 200 when API is up |
| Stream Processor | `GET /health` (FastAPI) | HTTP health check |
| Performance Controller | `GET /health` (FastAPI) | HTTP health check |
| OTel Collector | `http://localhost:13133/` | Health check endpoint (wget) |
| MinIO | `http://localhost:9000/minio/health/live` | Storage readiness |
| LocalStack | `http://localhost:4566/_localstack/health` | AWS emulation readiness |

---

## Deployment

### Local Development

Method: Docker Compose with composable profiles.

Prerequisites:
- Docker (with Docker Compose v2)
- Python 3.13
- Node.js 20
- Git LFS (OSRM map data)

Setup steps:

```bash
# Clone repository
git clone <repo>
git lfs pull

# Copy example env (optional — secrets are managed by secrets-init)
cp .env.example .env

# Start core + data pipeline + monitoring
docker compose -f infrastructure/docker/compose.yml \
  --profile core \
  --profile data-pipeline \
  --profile monitoring \
  up -d
```

### Production (AWS EKS)

Method: Terraform (infrastructure) + ArgoCD GitOps (workloads).

Region: `us-east-1`.

Deployment is triggered by the `deploy.yml` GitHub Actions workflow via `workflow_dispatch`.

### Environments

| Environment | Access | Branch | Notes |
|------------|--------|--------|-------|
| Development | `localhost` (Docker Compose) | any | LocalStack emulates AWS |
| Production | `*.ridesharing.portfolio.andresbrocco.com` | `deploy` | EKS + real AWS |

---

## Production Infrastructure (AWS)

### Three-Layer Terraform Model

```
bootstrap  (one-time, local state)
    creates: rideshare-tf-state-<account-id> S3 bucket

foundation  (long-lived, cost-free at rest)
    creates: VPC, subnets, security groups
             Route 53 hosted zone (ridesharing.portfolio.andresbrocco.com)
             ACM certificate (us-east-1, required by CloudFront)
             S3 buckets: bronze, silver, gold, checkpoints, frontend, logs, loki, tempo, build-assets
             ECR repositories (one per service)
             IAM roles (EKS node/cluster, per-workload Pod Identity roles, GitHub Actions OIDC role)
             AWS Secrets Manager secrets (rideshare/*)
             Glue Data Catalog databases (rideshare_bronze, rideshare_silver, rideshare_gold)
             CloudFront distribution (SPA origin from S3 frontend bucket)
             Lambda: rideshare-auth-deploy (timeout: 60s; handles visitor provisioning)
             EventBridge Scheduler role
             KMS CMK: rideshare-visitor-passwords (auto-rotation enabled; encrypts visitor passwords in DynamoDB)
             DynamoDB table: rideshare-visitors (PAY_PER_REQUEST, email hash key, PITR, KMS SSE)
             SES domain identity with DKIM/SPF/DMARC DNS records and production access provisioner

platform  (ephemeral — created on deploy, destroyed on teardown)
    creates: EKS cluster (rideshare-eks) + managed node group (t3.xlarge)
             EKS addons: aws-ebs-csi-driver, coredns, kube-proxy, vpc-cni, eks-pod-identity-agent
             RDS PostgreSQL (t4g.micro) — databases: airflow, metastore
             ALB controller (Helm)
             External Secrets Operator (Helm)
             kube-state-metrics (Helm)
             Pod Identity associations
```

Backend config: S3 bucket name is injected at `terraform init` time via `-backend-config="bucket=rideshare-tf-state-<ACCOUNT_ID>"`.

### IAM Model

EKS Pod Identity (not IRSA). All workload IAM roles trust `pods.eks.amazonaws.com` with `sts:AssumeRole` + `sts:TagSession`. Pod Identity associations are declared in `platform/main.tf` and bind `(cluster, namespace, service_account)` tuples to roles created in the foundation layer. No OIDC annotation is required on ServiceAccounts.

Exception: EBS CSI driver uses the node role (not Pod Identity) because the Pod Identity webhook may not be ready during initial cluster bootstrap.

### Frontend Delivery (Production)

React SPA built with Vite. Build output synced to S3 frontend bucket. Served via CloudFront CDN with Origin Access Control. HTML files cached with `max-age=0, must-revalidate`; static assets cached for 1 year.

### Kubernetes Namespace

All production workloads run in namespace `rideshare-prod`.

### Kubernetes Ingress

Ingress is not used. The platform uses `GatewayClass` (named `eg`, backed by Envoy Gateway) and `HTTPRoute` resources. All path-based routing strips the path prefix before forwarding — e.g., `/api/` rewrites to `/`. Two HTTPRoute files split responsibilities: `httproute-api.yaml` (simulation API, frontend root) and `httproute-web-services.yaml` (Airflow, Grafana, Prometheus, Trino UIs).

### Kubernetes Trino: Password File Bootstrap

In Kubernetes, the Trino pod runs a `setup-config` initContainer that:
1. Reads `TRINO_ADMIN_PASSWORD_HASH` and `TRINO_VISITOR_PASSWORD_HASH` from the `app-credentials` Kubernetes Secret (synced from Secrets Manager by ESO)
2. Renders `password.db.template` → `/tmp/trino-etc/password.db` with `chmod 600`
3. Renders `delta.properties.template` → `/tmp/trino-etc/catalog/delta.properties` with MinIO credentials

The `app-credentials` Secret is populated by ESO from two Secrets Manager paths (`rideshare/trino-admin-password-hash` and `rideshare/trino-visitor-password-hash`). These two secrets are **not** managed by Terraform — they are created by the deploy workflow and the visitor provisioning Lambda respectively.

### Grafana Admin Dashboard

A dedicated `Admin` Grafana folder is provisioned via the `grafana-dashboards-admin` ConfigMap, containing `visitor-activity.json`. This dashboard aggregates per-service visitor last-access timestamps:

| Panel Source | Mechanism |
|-------------|-----------|
| Airflow logins | `airflow-postgres` datasource querying `ab_user.last_login` |
| Grafana audit events | Loki (`GF_AUDIT_ENABLED=true` required) |
| Simulation API requests | Loki (via `RequestLoggerMiddleware` access logs) |
| Trino query activity | Loki (`QueryCompletedEvent` from event listener) |
| MinIO access | Loki (`MINIO_AUDIT_CONSOLE_ENABLE=on` required) |

The `airflow-postgres` datasource (uid: `airflow-postgres`) must be provisioned before Grafana starts — missing it causes Airflow login panels to fail silently.

### Kustomize Overlays

Two mutually exclusive production variants, selected by setting the ArgoCD Application `path` field:

| Overlay | Trino Catalog | DBT Runner | Extra Pods |
|---------|--------------|-----------|------------|
| `overlays/production-duckdb` | Hive Metastore (thrift, backed by RDS) | DuckDB | hive-metastore, postgres-metastore |
| `overlays/production-glue` | AWS Glue Data Catalog | Glue Interactive Sessions | none (hive-metastore omitted) |

Both overlays apply `components/aws-production/` which patches image tags, injects production ConfigMap values, configures EBS storage classes, and adds ALB ingress resources.

### ArgoCD GitOps

ArgoCD watches the `deploy` branch (`selfHeal: true`, `prune: true`). The deploy workflow force-pushes resolved manifests (placeholders substituted) to the `deploy` branch, which triggers ArgoCD reconciliation. Manual `kubectl` changes to managed resources are reverted within the 3-minute reconciliation interval.

Sync retry: exponential backoff (5s base, factor 2, max 3m, 5 attempts).

`ignoreDifferences` is configured for Deployment and StatefulSet replica counts, allowing manual scaling without ArgoCD reversion.

### Production Endpoints

| Service | URL |
|---------|-----|
| Control Panel | `https://control-panel.ridesharing.portfolio.andresbrocco.com` |
| API | `https://api.ridesharing.portfolio.andresbrocco.com` |
| Grafana | `https://grafana.ridesharing.portfolio.andresbrocco.com` |
| Airflow | `https://airflow.ridesharing.portfolio.andresbrocco.com` |
| Trino | `https://trino.ridesharing.portfolio.andresbrocco.com` |
| Prometheus | `https://prometheus.ridesharing.portfolio.andresbrocco.com` |
| Landing Page | `https://ridesharing.portfolio.andresbrocco.com` |

DNS: wildcard Route 53 ALIAS record `*.ridesharing.portfolio.andresbrocco.com` pointing to the ALB hostname. Created by the deploy workflow after ALB provisioning; deleted by the teardown workflow before `terraform destroy`.

### On-Demand Lifecycle (Lambda)

`rideshare-auth-deploy` Lambda (Python 3.13, Function URL with no AWS-layer auth, timeout 60s):

- Validates API key against Secrets Manager
- Dispatches `deploy.yml` or `teardown-platform.yml` via GitHub Actions REST API
- Tracks session state in SSM Parameter Store (`/rideshare/session/deadline`)
- Manages auto-teardown via EventBridge one-time schedule
- Aggregates per-service deploy readiness from the deploy workflow's progress reports (15 services)
- Cost tracking: hardcoded `$0.31/hour` (1x t3.xlarge); computed from elapsed session time
- **Two-phase visitor provisioning**: Phase 1 (`provision-visitor`, unauthenticated) stores durable visitor credentials in DynamoDB (KMS-encrypted plaintext password) and a PBKDF2 Trino password hash in Secrets Manager, then sends a SES welcome email — all before the platform is deployed. Phase 2 (`reprovision-visitors`, authenticated) is called by the deploy workflow post-deploy; it scans DynamoDB, decrypts passwords via KMS, and creates ephemeral service accounts in Grafana, Airflow, MinIO, and the Simulation API.

Session lifecycle: `deploying` → `active` (after frontend calls `activate-session`) → `tearing_down` → `gone`.

Session max duration: 2 hours, extendable/shrinkable in 15-minute increments.

Actions callable without an API key (`NO_AUTH_ACTIONS`): `session-status`, `auto-teardown`, `service-health`, `teardown-status`, `get-deploy-progress`, `provision-visitor`, `extend-session`, `shrink-session`. This allows visitor self-registration and frontend status polling to work without credentials.

Stale session guards: a `deploying` session older than 30 minutes is auto-deleted (assumes failed deploy); a `tearing_down` session older than 15 minutes is auto-deleted (assumes stale flag).

### Estimated Costs

| State | Approximate Cost |
|-------|----------------|
| Platform running (1 node) | ~$0.31/hour |
| Platform running (3 nodes) | ~$0.65/hour |
| Foundation only (no EKS/RDS) | ~$8/month |

---

## Data Platform Infrastructure

### Delta Table Registration

Delta Lake tables written by `bronze-ingestion` (via delta-rs) are not auto-discoverable by Trino or Glue.

| Script | Runtime | Method |
|--------|---------|--------|
| `infrastructure/scripts/register-delta-tables.sh` | Docker init container (Trino CLI) | `CALL delta.system.register_table(...)` |
| `infrastructure/scripts/register-trino-tables.py` | Airflow DAG (Trino REST API) | Same stored procedure via HTTP |
| `infrastructure/scripts/register-glue-tables.py` | Airflow DAG (boto3) | Glue catalog table creation |

In Kubernetes, `bronze-init` is a CronJob running every 10 minutes that calls `register_table` via Trino CLI. The operation is idempotent.

Note: DBT views (`anomalies_gps_outliers`, `anomalies_zombie_drivers`) have no `_delta_log` and cannot be registered as Trino Delta tables — they are excluded from all registration scripts.

### Trino Authentication and Access Control

Trino uses FILE-based password authentication (`http-server.authentication.type=PASSWORD`). Two accounts are defined:

| Account | Role | Access |
|---------|------|--------|
| `admin` | Full | All catalogs |
| `visitor` | Read-only | `delta` catalog only; `system` catalog blocked |

Password hashes (`TRINO_ADMIN_PASSWORD_HASH`, `TRINO_VISITOR_PASSWORD_HASH`) are injected as environment variables at container startup. The entrypoint copies `/etc/trino` to `/tmp/trino-etc/` (writability workaround), then renders `password.db.template` → `password.db` via `envsubst`/`sed` with `chmod 600`. The `file.refresh-period=5s` setting allows hash rotation without a restart; access control rules reload every 60s.

`rules.json` ordering is load-bearing: the `admin` full-access rule appears first, then the `system` deny for all users, then the `delta` read-only grant, then a catch-all read-only fallback.

### Visitor Account Provisioning

`infrastructure/scripts/provision_visitor_cli.py` orchestrates multi-service visitor account creation locally, delegating to three idempotent sub-modules:

| Sub-module | Service | Method |
|-----------|---------|--------|
| `provision_grafana_viewer.py` | Grafana | Admin API (`/api/admin/users`); HTTP 412 = update |
| `provision_airflow_viewer.py` | Airflow | REST API (`/api/v1/users`); HTTP 409 = update |
| `provision_minio_visitor.py` | MinIO | MinIO Admin SDK; policy from `infrastructure/policies/minio-visitor-readonly.json` (read-only on `rideshare-gold` bucket) |

Trino credentials are handled via bcrypt hash update in Secrets Manager (not direct service calls) and require a Trino container restart to take effect.

`generate_trino_password_hash.py` produces `$2b$10$...` prefixed hashes (Python bcrypt, cost factor 10). Trino's FILE authenticator accepts both `$2b$` and `$2y$` variants.

### Airflow DAGs

| DAG | Schedule | Purpose |
|-----|---------|---------|
| `dbt_silver_transformation` | Hourly | Bronze-to-Silver via DBT |
| `dbt_gold_transformation` | Triggered by Silver (daily in prod) | Silver-to-Gold star schema |
| `delta_maintenance` | Daily 03:00 | OPTIMIZE + VACUUM Delta tables |
| `dlq_monitoring` | Every 15 minutes | DLQ error count alert via DuckDB |

### MinIO (Local) / S3 (Production)

Local: MinIO at `localhost:9000` (UI at `localhost:9001`). S3-compatible.

Production S3 buckets (all prefixed `rideshare-<account-id>-`):

| Bucket Suffix | Purpose |
|--------------|---------|
| `bronze` | Raw Delta Lake tables (Bronze layer) |
| `silver` | Cleaned Delta Lake tables (Silver layer) |
| `gold` | Star schema Delta Lake tables (Gold layer) |
| `checkpoints` | Simulation SQLite checkpoint backups |
| `frontend` | React SPA build artifacts (CloudFront origin) |
| `logs` | Application logs archive |
| `loki` | Loki log storage backend |
| `tempo` | Tempo trace storage backend |
| `build-assets` | OSRM Sao Paulo map data (large binary) |

---

## Port Reference

### Host Ports (Docker Compose)

| Service | Host Port | Protocol |
|---------|-----------|---------|
| Simulation | 8000 | HTTP / WebSocket |
| Stream Processor | 8080 | HTTP |
| Control Panel | 5173 | HTTP |
| Kafka | 9092 | Kafka wire protocol (SASL/PLAIN) |
| Schema Registry | 8085 | HTTP |
| Redis | 6379 | Redis protocol |
| OSRM | 5000 | HTTP |
| MinIO API | 9000 | HTTP (S3-compatible) |
| MinIO Console | 9001 | HTTP |
| LocalStack | 4566 | HTTP (AWS API emulation) |
| Trino | 8084 | HTTP |
| Airflow | 8082 | HTTP |
| Hive Metastore | 9083 (internal only) | Thrift |
| PostgreSQL (Airflow) | 5432 | PostgreSQL wire protocol |
| PostgreSQL (Metastore) | 5433 | PostgreSQL wire protocol |
| Prometheus | 9090 | HTTP |
| Grafana | 3001 | HTTP |
| Loki | 3100 | HTTP |
| Tempo | 3200 | HTTP |
| cAdvisor | 8081 | HTTP |
| OTel Collector (internal telemetry) | 8888 | HTTP |
| OTel Collector (health check) | 13133 | HTTP |

---

## Development Commands

### Common Makefile Targets

| Command | Purpose |
|---------|---------|
| `make ci` | Full CI pipeline (lint + test + build) |
| `make lint` | All linting and type checking |
| `make test` | Unit tests + API contract validation |
| `make test-unit` | Simulation and stream-processor pytest |
| `make test-fast` | Unit tests excluding `@pytest.mark.slow` |
| `make test-api-contract` | OpenAPI spec export, validation, TypeScript type parity check |
| `make test-integration` | Docker Compose up, integration tests, cleanup |
| `make test-coverage` | pytest with HTML coverage report |
| `make build-frontend` | Vite production build |
| `make venvs` | Create all Python virtualenvs |
| `make lint-terraform` | TFLint for Terraform modules |
| `make clean` | Remove venvs, build artifacts, caches |

### Per-Service Commands

| Command | Purpose |
|---------|---------|
| `cd services/simulation && ./venv/bin/pytest` | Simulation unit tests |
| `cd services/stream-processor && ./venv/bin/pytest` | Stream processor unit tests |
| `cd services/control-panel && npm run test` | Frontend tests (Vitest) |
| `cd services/control-panel && npm run lint` | Frontend ESLint |
| `cd tools/dbt && ./venv/bin/dbt test` | DBT schema + custom tests |
| `./venv/bin/pytest tests/integration/` | Integration tests |
| `./venv/bin/ruff check src/ tests/` | Python linting |
| `./venv/bin/black src/ tests/` | Python formatting |
| `./venv/bin/mypy src/` | Python type checking |

### Soft Reset (Production)

To wipe all data while keeping the EKS cluster running:

```bash
# Via GitHub Actions UI:
# Trigger: soft-reset.yml workflow_dispatch
# Input: confirmation="RESET", dbt_runner=<duckdb|glue>

# Wipes: Kafka PVCs, S3 lakehouse buckets, RDS airflow/metastore DBs,
#         Redis, Prometheus/Loki/Tempo emptyDir volumes
# Preserves: EKS cluster, ALB, ECR images, Secrets Manager, S3 build-assets
```

### Teardown (Production)

```bash
# Via GitHub Actions UI:
# Trigger: teardown-platform.yml workflow_dispatch

# Destroys: EKS cluster, RDS, ALB, EBS volumes, Route 53 wildcard record
# Preserves: S3 lakehouse data, ECR images, Secrets Manager, Route 53 zone,
#            CloudFront distribution, ACM certificate (foundation layer intact)
```
