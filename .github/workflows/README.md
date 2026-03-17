# GitHub Actions Workflows

> CI/CD automation for the rideshare simulation platform: continuous integration, Docker image builds, AWS platform deployment, Lambda deploys, and operational reset/teardown workflows.

## Quick Reference

### Workflows

| File | Name | Trigger | Purpose |
|------|------|---------|---------|
| `ci.yml` | CI | Push/PR to `main` | Lint, type-check, unit tests, frontend build, API contract validation |
| `build-images.yml` | Build Images | Push to `main` (path-filtered) or `workflow_dispatch` | Build and push Docker images to ECR |
| `deploy.yml` | Deploy | `workflow_dispatch` | Full platform deploy to EKS + optional frontend to S3/CloudFront |
| `deploy-lambda.yml` | Deploy Lambda | Push to `main` (`services/auth-deploy/**`, `services/ai-chat/**`) or `workflow_dispatch` | Package and deploy `rideshare-auth-deploy` Lambda |
| `integration-tests.yml` | Integration Tests | Weekly (Monday 02:00 UTC) or `workflow_dispatch` | Full-stack integration tests with Docker Compose |
| `soft-reset.yml` | Soft Reset | `workflow_dispatch` | Wipe all runtime data without destroying infrastructure |
| `teardown-platform.yml` | Teardown Platform | `workflow_dispatch` | Destroy EKS platform (preserves foundation resources) |

---

### Required GitHub Secrets

| Secret | Used By | Purpose |
|--------|---------|---------|
| `AWS_ACCOUNT_ID` | All workflows | AWS account number for OIDC role ARN and resource naming |
| `GH_DEPLOY_PAT` | `deploy.yml` | GitHub PAT synced to Secrets Manager for Lambda to trigger future deploys |
| `OWNER_REPLY_TO_EMAIL` | `deploy.yml` | Email address used in Terraform foundation plan |

### AWS OIDC Role

All workflows authenticate via OIDC (no long-lived keys):

```
arn:aws:iam::<AWS_ACCOUNT_ID>:role/rideshare-github-actions
```

Region: `us-east-1` for all workflows.

---

### Workflow Inputs

#### Deploy (`deploy.yml`)

| Input | Type | Options | Default | Description |
|-------|------|---------|---------|-------------|
| `action` | choice | `deploy-all`, `deploy-platform`, `deploy-frontend` | — | What to deploy |
| `dbt_runner` | choice | `duckdb`, `glue` | `duckdb` | Controls Kustomize overlay and Airflow target |

#### Build Images (`build-images.yml`)

| Input | Type | Options | Default | Description |
|-------|------|---------|---------|-------------|
| `scope` | choice | `all`, `simulation`, `stream-processor`, `control-panel`, `bronze-ingestion`, `hive-metastore`, `performance-controller`, `osrm`, `otel-collector` | — | Which service(s) to build |

#### Soft Reset (`soft-reset.yml`)

| Input | Type | Description |
|-------|------|-------------|
| `confirmation` | string | Must be exactly `RESET` to proceed |
| `dbt_runner` | choice | `duckdb` or `glue` — must match the running deploy |

---

### Deployed Service Images

The following ECR repositories are managed by `build-images.yml`:

| Service | ECR Repository | Notes |
|---------|----------------|-------|
| simulation | `rideshare/simulation` | Includes `schemas/` copied into build context |
| stream-processor | `rideshare/stream-processor` | — |
| control-panel | `rideshare/control-panel` | Bakes production URLs via `--build-arg` |
| bronze-ingestion | `rideshare/bronze-ingestion` | — |
| hive-metastore | `rideshare/hive-metastore` | — |
| performance-controller | `rideshare/performance-controller` | — |
| osrm | `rideshare/osrm` | Fetches map data from S3 (`rideshare-<account>-build-assets`) or Git LFS |
| otel-collector | `rideshare/otel-collector` | — |

Images are tagged with `github.sha` and `latest`. Build cache uses registry mode (`buildcache` tag per repo).

---

### Production URLs (After Deploy)

| Service | URL |
|---------|-----|
| Landing Page | `https://ridesharing.portfolio.andresbrocco.com` |
| Control Panel | `https://control-panel.ridesharing.portfolio.andresbrocco.com` |
| Simulation API | `https://api.ridesharing.portfolio.andresbrocco.com` |
| Grafana | `https://grafana.ridesharing.portfolio.andresbrocco.com` |
| Airflow | `https://airflow.ridesharing.portfolio.andresbrocco.com` |
| Trino | `https://trino.ridesharing.portfolio.andresbrocco.com` |
| Prometheus | `https://prometheus.ridesharing.portfolio.andresbrocco.com` |

DNS: Route 53 wildcard ALIAS `*.ridesharing.portfolio.andresbrocco.com` → ALB.

---

### Terraform Versions

| Tool | Version |
|------|---------|
| Terraform | `1.14.3` |
| TFLint | Latest (via `setup-tflint@v4`) |

---

## Common Tasks

### Deploy the full platform

1. Ensure all service images are built (run `Build Images` workflow with `scope: all` if needed)
2. Run the `Deploy` workflow with `action: deploy-all` and `dbt_runner: duckdb`
3. Wait ~30-60 minutes for EKS convergence
4. Activate the simulation manually after deploy:

```bash
# Replace <API_KEY> with the value from rideshare/api-key in Secrets Manager
curl -X POST https://api.ridesharing.portfolio.andresbrocco.com/simulation/start \
  -H "X-API-Key: <API_KEY>"

curl -X POST https://api.ridesharing.portfolio.andresbrocco.com/agents/drivers \
  -H "X-API-Key: <API_KEY>"

curl -X POST https://api.ridesharing.portfolio.andresbrocco.com/agents/riders \
  -H "X-API-Key: <API_KEY>"
```

### Deploy only the frontend

Run the `Deploy` workflow with `action: deploy-frontend`. This builds the React app and syncs to S3, then invalidates CloudFront.

### Build and push a single service image

Run the `Build Images` workflow with `workflow_dispatch`, selecting the target `scope` (e.g. `simulation`).

### Reset all runtime data without destroying infrastructure

Run the `Soft Reset` workflow:
- Input `confirmation`: `RESET`
- Input `dbt_runner`: must match what was used in the last deploy

What gets wiped: Kafka topics, S3 lakehouse buckets (bronze/silver/gold/checkpoints), RDS airflow and metastore databases, Redis, and monitoring data (Prometheus/Loki/Tempo).

What is preserved: EKS cluster, RDS instance, ALB, ECR images, Secrets Manager, build-assets S3.

### Teardown the platform (cost savings)

Run the `Teardown Platform` workflow. This destroys EKS, RDS, ALB, EC2 nodes, and EBS volumes.

Preserved after teardown: S3 lakehouse data, ECR images, Secrets Manager, Route 53 hosted zone, CloudFront, ACM certificate.

Estimated cost at foundation-only state: ~$8/month.

### Deploy Lambda only

Push changes to `services/auth-deploy/**` or `services/ai-chat/**` on `main`, or run the `Deploy Lambda` workflow manually. The workflow packages dependencies flat at the zip root (not nested under `auth-deploy/`) so Lambda imports work correctly.

---

## CI Pipeline

The `CI` workflow runs on every push and PR to `main` with two parallel tracks after `lint-and-typecheck` passes:

```
lint-and-typecheck
    ├── unit-tests (simulation + stream-processor pytest, frontend Vitest)
    ├── frontend-build (npm run build)
    └── api-contract-validation (only when API-related paths change)
```

CI runs `pre-commit --all-files`, which covers:
- Python: ruff, black, mypy (per-service venvs)
- Terraform: tflint
- Frontend: TypeScript + ESLint (via npm ci + build)

API contract validation exports the OpenAPI spec, validates it, generates TypeScript types, and asserts they match.

---

## Integration Tests

The `integration-tests.yml` workflow runs weekly (Monday 02:00 UTC) against a full local Docker Compose stack.

Environment variables set during the run:

| Variable | Value |
|----------|-------|
| `MINIO_ENDPOINT` | `http://localhost:9000` |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` |
| `SCHEMA_REGISTRY_URL` | `http://localhost:8085` |
| `LOCALSTACK_ENDPOINT` | `http://localhost:4566` |
| `AWS_ENDPOINT_URL` | `http://localhost:4566` |
| `AWS_ACCESS_KEY_ID` | `test` |
| `AWS_SECRET_ACCESS_KEY` | `test` |
| `AWS_DEFAULT_REGION` | `us-east-1` |
| `SIM_SPEED_MULTIPLIER` | `10` |
| `SIM_LOG_LEVEL` | `DEBUG` |

Credentials are loaded dynamically from LocalStack Secrets Manager after `secrets-init` completes. Test results are uploaded as artifacts (`nightly-test-results`, 30-day retention).

---

## Deploy Pipeline Internals

The `deploy.yml` platform job performs these steps in order:

1. Verify Foundation State (Terraform plan must show no drift)
2. Reconcile Terraform state (safe imports of pre-existing resources)
3. Terraform Apply (platform module: EKS, RDS, ALB)
4. Ensure all service images exist at the deploy SHA (retags `latest` if SHA tag is missing)
5. Resolve production values (account ID, ACM cert, ALB SG) and substitute placeholders in Kubernetes YAML
6. Package dbt and Great Expectations projects as tarballs into the production component
7. Push resolved manifests to the `deploy` branch (ArgoCD watches this branch with `selfHeal: true`)
8. Install/upgrade ArgoCD (v3.2.3)
9. Apply the ArgoCD Application manifest
10. Wait for services in phases: Infrastructure → Schema/Config → Application → Data Pipeline → UI
11. Report each service ready status to the `rideshare-auth-deploy` Lambda
12. Ensure auto-teardown session exists
13. Re-provision visitor Grafana/Airflow/MinIO/Simulation API accounts from DynamoDB
14. Create Route 53 wildcard ALIAS record

---

## Troubleshooting

**Foundation has unapplied changes**
The deploy job will fail at "Verify Foundation State". Run `terraform apply` locally in `infrastructure/terraform/foundation/` before re-running the workflow.

**State lock on deploy failure**
```bash
AWS_PROFILE=rideshare terraform force-unlock -force <LOCK_ID> -chdir=infrastructure/terraform/platform
```

**Service image missing at deploy SHA**
The deploy job auto-retags `latest` → `<sha>`. If no `latest` exists, manually run `Build Images` for that service first.

**ALB webhook blocks deployments**
The deploy job auto-deletes stale `aws-load-balancer-webhook` mutating/validating configs if the ALB controller is not ready within 120s.

**OSRM build fails with pointer file**
The `osrm` image build pulls `sao-paulo-metro.osm.pbf` from S3 (`rideshare-<account>-build-assets/osrm/`). If S3 cache misses, it falls back to Git LFS. If LFS returns a pointer file (< 1 MB), the build fails — ensure LFS is configured and the file is properly tracked.

**Soft reset: ArgoCD reverts changes**
Auto-sync is suspended at the start of the reset and restored at the end (with a hard refresh). If the workflow fails mid-run, manually restore sync:
```bash
kubectl patch application rideshare-platform -n argocd \
  --type merge -p '{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true,"allowEmpty":false}}}}'
```

**GH_DEPLOY_PAT not set warning**
The `deploy.yml` job will print a warning but continue. The Lambda-triggered auto-teardown feature requires this PAT to call back into GitHub Actions.

---

## Related

- [CONTEXT.md](../../CONTEXT.md) — Project architecture overview
- [README.md](../../README.md) — Root quick-start, all local commands, ports
- [infrastructure/terraform/README.md](../../infrastructure/terraform/README.md) — Terraform modules reference (if present)
- [services/auth-deploy/](../../services/auth-deploy/) — Lambda source for visitor provisioning and auto-teardown
- [docs/INFRASTRUCTURE.md](../../docs/INFRASTRUCTURE.md) — Docker, Kubernetes, CI/CD architecture
