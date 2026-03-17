# infrastructure/kubernetes/overlays

> Two mutually exclusive Kustomize overlays producing complete ArgoCD-deployable production targets, differentiated by DBT runner catalog backend (Hive Metastore vs AWS Glue).

## Quick Reference

### Overlay Variants

| Overlay | DBT Runner | Trino Catalog Backend | Hive Metastore Pod | RDS Metastore DB |
|---|---|---|---|---|
| `production-duckdb` | `duckdb` | Hive Metastore thrift (`thrift://hive-metastore:9083`) | Yes | Yes |
| `production-glue` | `glue` | AWS Glue Data Catalog | No | No |

### Environment Variables

These env vars are injected into Kubernetes Deployments by the overlays. Values must be sourced from Terraform outputs before deploying.

| Variable | Overlay | Target Workloads | Source |
|---|---|---|---|
| `DBT_RUNNER` | `production-glue` | `airflow-scheduler`, `airflow-webserver` | Hardcoded `"glue"` |
| `GLUE_ROLE_ARN` | `production-glue` | `airflow-scheduler`, `airflow-webserver` | Terraform output (see below) |
| `POSTGRES_METASTORE_USER` | `production-duckdb` | `hive-metastore` | Kubernetes Secret (via `aws-production` component) |
| `POSTGRES_METASTORE_PASSWORD` | `production-duckdb` | `hive-metastore` | Kubernetes Secret (via `aws-production` component) |
| `AWS_REGION` | both | `hive-metastore`, `trino` | Hardcoded `"us-east-1"` |

### Placeholders Requiring Substitution

The following literal tokens appear in patch files and **must be replaced** with Terraform outputs before `kubectl apply` or ArgoCD sync:

| Placeholder | File | Terraform Command |
|---|---|---|
| `<rds-endpoint>` | `production-duckdb/hive-metastore-patch.yaml`, `production-duckdb/hive-site-config-patch.yaml` | `terraform -chdir=infrastructure/terraform/platform output -raw rds_endpoint` |
| `<account-id>` | `production-duckdb/hive-site-config-patch.yaml` | AWS account ID (not a Terraform output) |
| `<image-tag>` | `production-duckdb/kustomization.yaml` | CI/CD build pipeline output |
| `<glue-role-arn>` | `production-glue/kustomization.yaml` | `terraform -chdir=infrastructure/terraform/foundation output -raw glue_job_role_arn` |

### Commands

**Preview rendered manifests (production-duckdb):**
```bash
kubectl kustomize infrastructure/kubernetes/overlays/production-duckdb
```

**Preview rendered manifests (production-glue):**
```bash
kubectl kustomize infrastructure/kubernetes/overlays/production-glue
```

**Apply production-duckdb directly (after placeholder substitution):**
```bash
kubectl apply -k infrastructure/kubernetes/overlays/production-duckdb
```

**Apply production-glue directly (after placeholder substitution):**
```bash
kubectl apply -k infrastructure/kubernetes/overlays/production-glue
```

**Get the Glue role ARN from Terraform:**
```bash
terraform -chdir=infrastructure/terraform/foundation output -raw glue_job_role_arn
```

**Get the RDS endpoint from Terraform:**
```bash
terraform -chdir=infrastructure/terraform/platform output -raw rds_endpoint
```

### Configuration Files

| File | Purpose |
|---|---|
| `production-duckdb/kustomization.yaml` | Root Kustomize entrypoint for the DuckDB/Hive variant |
| `production-glue/kustomization.yaml` | Root Kustomize entrypoint for the Glue variant |
| `production-duckdb/hive-metastore-patch.yaml` | Patches Hive Metastore Deployment to use RDS and IRSA |
| `production-duckdb/hive-site-config-patch.yaml` | Patches `hive-site-config` ConfigMap for AWS S3 via IRSA |
| `production-duckdb/trino-catalog-patch.yaml` | Patches `trino-config` ConfigMap with Hive thrift URI |
| `production-glue/trino-glue-catalog-patch.yaml` | Patches Trino Deployment to use Glue ConfigMap and removes Hive/MinIO init containers |

### Prerequisites

- Terraform infrastructure provisioned (`infrastructure/terraform/platform` and `infrastructure/terraform/foundation`)
- IRSA (IAM Roles for Service Accounts) or Pod Identity associations configured for `hive-metastore`, `trino`, and `airflow` service accounts
- `aws-production` Kustomize component available at `infrastructure/kubernetes/components/aws-production`
- All placeholder tokens (`<rds-endpoint>`, `<account-id>`, `<image-tag>`, `<glue-role-arn>`) substituted before applying
- `ADMIN_PASSWORD` available in the `app-credentials` Kubernetes Secret (synced from the `data-pipeline` secret via ESO) — required by both overlays for Trino FILE-based authentication (the admin bcrypt hash is computed at pod startup by the `setup-config` initContainer via `htpasswd`)
- Grafana `airflow-postgres` datasource (uid: `airflow-postgres`) provisioned — required by the `visitor-activity.json` dashboard in the inherited Grafana Admin folder; without it, Airflow login panels in that dashboard will fail silently

## Common Tasks

### Choose which overlay to deploy

Use `production-duckdb` when:
- You want the full self-hosted stack (Hive Metastore + RDS metastore database)
- Your dbt transformations run locally inside the Airflow container using DuckDB

Use `production-glue` when:
- You want to offload dbt jobs to AWS Glue (lower Kubernetes resource footprint)
- You do not want to operate or pay for Hive Metastore and its RDS database

> These overlays are mutually exclusive. Never apply both to the same namespace simultaneously.

### Substitute placeholders before deploying (production-duckdb)

```bash
RDS_ENDPOINT=$(terraform -chdir=infrastructure/terraform/platform output -raw rds_endpoint)
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile rideshare)
IMAGE_TAG=<your-build-tag>

sed -i "s/<rds-endpoint>/$RDS_ENDPOINT/g" \
  infrastructure/kubernetes/overlays/production-duckdb/hive-metastore-patch.yaml \
  infrastructure/kubernetes/overlays/production-duckdb/hive-site-config-patch.yaml

sed -i "s/<account-id>/$ACCOUNT_ID/g" \
  infrastructure/kubernetes/overlays/production-duckdb/hive-site-config-patch.yaml

sed -i "s/<image-tag>/$IMAGE_TAG/g" \
  infrastructure/kubernetes/overlays/production-duckdb/kustomization.yaml
```

### Substitute placeholders before deploying (production-glue)

```bash
GLUE_ROLE_ARN=$(terraform -chdir=infrastructure/terraform/foundation output -raw glue_job_role_arn)

sed -i "s|<glue-role-arn>|$GLUE_ROLE_ARN|g" \
  infrastructure/kubernetes/overlays/production-glue/kustomization.yaml
```

### Verify Trino catalog configuration

After applying the overlay, check which ConfigMap Trino's `setup-config` init container is reading from:

```bash
kubectl get deployment trino -n rideshare-prod -o jsonpath='{.spec.template.spec.volumes[?(@.name=="config-source")].configMap.name}'
# production-duckdb: trino-config
# production-glue:   trino-config-glue
```

### Check Hive Metastore connectivity (production-duckdb only)

```bash
# Confirm Hive Metastore is listening on thrift port 9083
kubectl exec -n rideshare-prod deploy/trino -- nc -zv hive-metastore 9083
```

## Troubleshooting

### Hive Metastore fails to start with XML parse error

Cause: An RDS password containing XML-special characters (`&`, `<`, `>`) was written directly into `hive-site.xml` rather than passed via `SERVICE_OPTS` JVM properties.

Fix: The `hive-metastore-patch.yaml` in `production-duckdb` already routes credentials through `SERVICE_OPTS` at container startup (not via `hive-site.xml`). Verify `POSTGRES_METASTORE_PASSWORD` is injected via Kubernetes Secret, not hardcoded in the patch file.

### Trino cannot reach Hive Metastore (connection refused on 9083)

Cause: The `production-glue` overlay was applied instead of `production-duckdb`, so the Hive Metastore pod was not deployed.

Fix: Confirm the correct overlay is active:
```bash
kubectl get pods -n rideshare-prod -l app=hive-metastore
```
If no pods exist, redeploy with `production-duckdb`.

### dbt-glue jobs fail with "role not found" or assume-role error

Cause: `<glue-role-arn>` placeholder was not substituted before deploying, or the injected ARN is incorrect.

Fix: Check the env var on the Airflow scheduler:
```bash
kubectl exec -n rideshare-prod deploy/airflow-scheduler -- env | grep GLUE_ROLE_ARN
```
The value must be a valid ARN (`arn:aws:iam::<account-id>:role/<role-name>`), not the literal `<glue-role-arn>` placeholder.

### `wait-for-hive-metastore` init container error in production-glue

Cause: Both `trino-catalog-patch.yaml` (duckdb) and `trino-glue-catalog-patch.yaml` (glue) were applied simultaneously, creating a conflicting init container sequence.

Fix: These patches are mutually exclusive. Each overlay must apply only its own Trino patch. Rerender the overlay from a clean state:
```bash
kubectl kustomize infrastructure/kubernetes/overlays/production-glue | kubectl apply -f -
```

### `delta.register-table-procedure.enabled` not set (production-duckdb)

Cause: The Trino catalog patch was not applied or was overridden.

Fix: Verify `delta.register-table-procedure.enabled=true` is present in the rendered ConfigMap:
```bash
kubectl get configmap trino-config -n rideshare-prod -o jsonpath='{.data.delta\.properties\.template}'
```

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context for this directory
- [production-duckdb/CONTEXT.md](production-duckdb/CONTEXT.md) — DuckDB/Hive variant details
- [production-glue/CONTEXT.md](production-glue/CONTEXT.md) — Glue variant details
- [infrastructure/kubernetes/components/aws-production](../components/aws-production/CONTEXT.md) — Shared AWS production component
- [infrastructure/kubernetes/manifests](../manifests/CONTEXT.md) — Base Kubernetes resource definitions
- [infrastructure/kubernetes/argocd](../argocd/CONTEXT.md) — ArgoCD application definitions that reference these overlays
