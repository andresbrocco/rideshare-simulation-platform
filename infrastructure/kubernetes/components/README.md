# Kubernetes Components

> Reusable Kustomize Component definitions that bundle AWS-production-specific patches into a single composable unit consumed by multiple overlays.

## Quick Reference

### Production Subdomains (ALB IngressGroup)

All ingress objects share `alb.ingress.kubernetes.io/group.name: rideshare`, which consolidates them into a single AWS ALB.

| Service | URL | ALB Health Check Path | Backend Port |
|---|---|---|---|
| Simulation API | `https://api.ridesharing.portfolio.andresbrocco.com` | `/health` | 8000 |
| Control Panel | `https://control-panel.ridesharing.portfolio.andresbrocco.com` | `/` | 80 |
| Grafana | `https://grafana.ridesharing.portfolio.andresbrocco.com` | `/api/health` | 3001 |
| Airflow | `https://airflow.ridesharing.portfolio.andresbrocco.com` | `/api/v2/monitor/health` | 8082 |
| Trino | `https://trino.ridesharing.portfolio.andresbrocco.com` | `/v1/info` | 8080 |
| Prometheus | `https://prometheus.ridesharing.portfolio.andresbrocco.com` | `/-/healthy` | 9090 |

### Environment Variables Patched for Production

These variables are injected via ConfigMap patches or direct container env overrides. All values marked `<placeholder>` are substituted by the CI deploy workflow.

#### `core-config` ConfigMap (applies to all core services)

| Variable | Production Value |
|---|---|
| `CORS_ORIGINS` | `https://ridesharing.portfolio.andresbrocco.com,https://control-panel.ridesharing.portfolio.andresbrocco.com` |
| `DEPLOYMENT_ENV` | `production` |

#### `data-pipeline-config` ConfigMap (Airflow, Hive Metastore, Bronze Ingestion)

| Variable | Production Value |
|---|---|
| `AWS_REGION` | `us-east-1` |
| `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` | `postgresql+psycopg2://airflow:CHANGEME@<rds-endpoint>:5432/airflow` |
| `HIVE_METASTORE_DB_URL` | `jdbc:postgresql://<rds-endpoint>:5432/metastore` |
| `AIRFLOW_POSTGRES_HOST` | `<rds-endpoint>` |
| `POSTGRES_METASTORE_HOST` | `<rds-endpoint>` |
| `BRONZE_BUCKET` | `rideshare-<account-id>-bronze` |
| `MINIO_ENDPOINT` | _(empty — MinIO removed)_ |
| `LOCALSTACK_ENDPOINT` | _(empty — LocalStack removed)_ |

#### Simulation Deployment (direct container env, overrides ConfigMap)

| Variable | Production Value |
|---|---|
| `DEPLOYMENT_ENV` | `production` |
| `SIM_SPEED_MULTIPLIER` | `8` |
| `SIM_CHECKPOINT_STORAGE_TYPE` | `s3` |
| `SIM_CHECKPOINT_S3_BUCKET` | `rideshare-<account-id>-checkpoints` |
| `SIM_CHECKPOINT_S3_PREFIX` | `simulation` |
| `SIM_RESUME_FROM_CHECKPOINT` | `true` |
| `AWS_REGION` | `us-east-1` |
| `MALFORMED_EVENT_RATE` | `0.05` |

### ECR Image Placeholders

All custom service images reference ECR. Placeholders are resolved by the deploy workflow via `kustomize edit set image`.

| Image Name | ECR Repository |
|---|---|
| `rideshare-simulation` | `<account-id>.dkr.ecr.us-east-1.amazonaws.com/rideshare/simulation:<image-tag>` |
| `rideshare-stream-processor` | `<account-id>.dkr.ecr.us-east-1.amazonaws.com/rideshare/stream-processor:<image-tag>` |
| `rideshare-performance-controller` | `<account-id>.dkr.ecr.us-east-1.amazonaws.com/rideshare/performance-controller:<image-tag>` |
| `rideshare-control-panel` | `<account-id>.dkr.ecr.us-east-1.amazonaws.com/rideshare/control-panel:<image-tag>` |
| `rideshare-bronze-ingestion` | `<account-id>.dkr.ecr.us-east-1.amazonaws.com/rideshare/bronze-ingestion:<image-tag>` |
| `rideshare-osrm` | `<account-id>.dkr.ecr.us-east-1.amazonaws.com/rideshare/osrm:<image-tag>` |
| `otel/opentelemetry-collector-contrib` | `<account-id>.dkr.ecr.us-east-1.amazonaws.com/rideshare/otel-collector:<image-tag>` |

### Pod Identity ServiceAccounts

These ServiceAccounts are declared in `aws-production/serviceaccount-irsa-patches.yaml`. IAM permissions are injected via EKS Pod Identity (not IRSA). No `eks.amazonaws.com/role-arn` annotation is set — adding one would break the trust policies configured in Terraform.

| ServiceAccount | Namespace | Bound To |
|---|---|---|
| `simulation` | `rideshare-prod` | Simulation Deployment |
| `bronze-ingestion` | `rideshare-prod` | Bronze Ingestion Deployment |
| `airflow-scheduler` | `rideshare-prod` | Airflow Scheduler Deployment |
| `airflow-webserver` | `rideshare-prod` | Airflow Webserver Deployment |
| `trino` | `rideshare-prod` | Trino Deployment |
| `hive-metastore` | `rideshare-prod` | Hive Metastore Deployment |
| `loki` | `rideshare-prod` | Loki Deployment |
| `tempo` | `rideshare-prod` | Tempo Deployment |
| `external-secrets` | `external-secrets` | External Secrets Operator |

### Storage

| StorageClass | Provisioner | Type | Notes |
|---|---|---|---|
| `rideshare-storage` | `ebs.csi.aws.com` | `gp3`, encrypted | Set as cluster default; replaces `local-path` from K3s/kind |

Kafka's `kafka-patch.yaml` upgrades Kafka's volume from `emptyDir` to a 10 Gi EBS-backed `PVC` via `volumeClaimTemplates`. This change is irreversible once applied — resizing requires manual PVC intervention.

### Configuration Files

| File | Purpose |
|---|---|
| `aws-production/kustomization.yaml` | Component root — declares resources, patches, images, configMapGenerators |
| `aws-production/configmap-core-patch.yaml` | Production CORS and deployment env for core services |
| `aws-production/configmap-data-pipeline-patch.yaml` | RDS endpoints, S3 bucket, AWS region for data pipeline |
| `aws-production/simulation-patch.yaml` | S3 checkpoints, speed multiplier, CORS for simulation |
| `aws-production/serviceaccount-irsa-patches.yaml` | Pod Identity ServiceAccounts for all IAM-enabled workloads |
| `aws-production/secretstore-aws-patch.yaml` | AWS Secrets Manager SecretStore (node-role credentials, not Pod Identity) |
| `aws-production/storageclass-ebs.yaml` | Default EBS gp3 StorageClass replacing local-path provisioner |
| `aws-production/ingress-api.yaml` | ALB Ingress for Simulation API |
| `aws-production/ingress-grafana.yaml` | ALB Ingress for Grafana |
| `aws-production/ingress-airflow.yaml` | ALB Ingress for Airflow |
| `aws-production/ingress-trino.yaml` | ALB Ingress for Trino |
| `aws-production/ingress-prometheus.yaml` | ALB Ingress for Prometheus |
| `aws-production/ingress-control-panel.yaml` | ALB Ingress for Control Panel |

### Prerequisites

- AWS Load Balancer Controller installed in the cluster
- External Secrets Operator installed in `external-secrets` namespace
- EBS CSI driver installed
- Terraform platform module applied — provides Pod Identity associations, RDS endpoint, ALB SG, ACM cert ARN
- Secrets present in AWS Secrets Manager (see `infrastructure/kubernetes/manifests/external-secrets-*.yaml`)

## Common Tasks

### Apply This Component to an Overlay

This component is not applied directly — it is referenced in an overlay's `kustomization.yaml`:

```yaml
components:
  - ../../components/aws-production
```

### Preview the Rendered Manifests

```bash
# From an overlay directory (e.g., production-duckdb)
kubectl kustomize infrastructure/kubernetes/overlays/production-duckdb --enable-alpha-plugins
```

### Substitute Placeholders Before Apply (CI Step)

The deploy workflow performs these substitutions before running `kubectl apply`:

```bash
# Inside the overlay directory
kustomize edit set image \
  rideshare-simulation=123456789.dkr.ecr.us-east-1.amazonaws.com/rideshare/simulation:abc1234 \
  rideshare-stream-processor=123456789.dkr.ecr.us-east-1.amazonaws.com/rideshare/stream-processor:abc1234
  # ...repeat for each image

# Substitute ALB security group and ACM cert ARN in ingress files
sed -i "s|<alb-sg-id>|sg-0abc123|g" infrastructure/kubernetes/components/aws-production/ingress-api.yaml
sed -i "s|<acm-cert-arn>|arn:aws:acm:us-east-1:123456789:certificate/...|g" \
  infrastructure/kubernetes/components/aws-production/ingress-*.yaml

# Substitute RDS endpoint in data-pipeline ConfigMap
sed -i "s|<rds-endpoint>|mydb.cluster.us-east-1.rds.amazonaws.com|g" \
  infrastructure/kubernetes/components/aws-production/configmap-data-pipeline-patch.yaml
```

### Regenerate ConfigMap Tarballs

When the DBT project or Great Expectations suite changes, rebuild the tarballs so ArgoCD picks up the new content:

```bash
# DBT project tarball
cd tools/dbt
tar czf ../../infrastructure/kubernetes/components/aws-production/dbt-project.tar.gz .

# Great Expectations tarball
cd tools/great-expectations
tar czf ../../infrastructure/kubernetes/components/aws-production/ge-project.tar.gz .
```

Then commit both `.tar.gz` files — ArgoCD manages these as Kustomize ConfigMap resources.

### Verify ALB Health Checks

After deployment, confirm each service passes its ALB health check:

```bash
curl -sI https://api.ridesharing.portfolio.andresbrocco.com/health
curl -sI https://grafana.ridesharing.portfolio.andresbrocco.com/api/health
curl -sI https://airflow.ridesharing.portfolio.andresbrocco.com/api/v2/monitor/health
curl -sI https://trino.ridesharing.portfolio.andresbrocco.com/v1/info
curl -sI https://prometheus.ridesharing.portfolio.andresbrocco.com/-/healthy
```

## Troubleshooting

**Pod fails to start with AWS credential errors**
- Confirm the Pod Identity association exists in Terraform: `aws eks list-pod-identity-associations --cluster-name <cluster> --profile rideshare`
- Confirm the ServiceAccount name matches exactly (case-sensitive). Do not add `eks.amazonaws.com/role-arn` annotations — this would re-enable IRSA and break the Pod Identity trust policy.

**External Secrets not syncing**
- The `secretstore-aws-patch.yaml` SecretStore uses node-role credentials, not Pod Identity. Verify the EKS node IAM role has `secretsmanager:GetSecretValue` permission.
- Check ESO controller logs: `kubectl logs -n external-secrets deploy/external-secrets`

**Kafka data loss after pod restart**
- If Kafka is using `emptyDir` (base manifest default), this component's `kafka-patch.yaml` must have been applied to replace it with an EBS PVC. Confirm with: `kubectl get pvc -n rideshare-prod`

**ALB shows 404 or 502 for a service**
- Confirm `<alb-sg-id>` and `<acm-cert-arn>` were substituted in the ingress files before apply.
- Check ALB target group health in the AWS Console — each ingress has its own target group within the shared ALB (IngressGroup `rideshare`).
- Confirm the backend Service and port match the ingress spec.

**MinIO env vars still present after deploy**
- The `configmap-data-pipeline-patch.yaml` sets `MINIO_ENDPOINT: ""` and `LOCALSTACK_ENDPOINT: ""`. If a service still reads a non-empty value, a higher-precedence env var (direct container spec) may be overriding it.

**StorageClass conflict**
- `storageclass-ebs.yaml` sets itself as the cluster default. If another default StorageClass exists, Kubernetes will reject the annotation. Remove the default annotation from the existing StorageClass first.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context for this directory
- [aws-production/CONTEXT.md](aws-production/CONTEXT.md) — Detailed context for the aws-production component
- [infrastructure/kubernetes/manifests](../manifests/CONTEXT.md) — Base Kubernetes manifests this component patches
- [infrastructure/kubernetes/overlays](../overlays/CONTEXT.md) — Overlays that consume this component
- [infrastructure/terraform/platform](../../terraform/platform/CONTEXT.md) — Terraform that provisions Pod Identity associations, RDS, ALB
