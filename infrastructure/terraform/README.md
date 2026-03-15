# infrastructure/terraform

> AWS production infrastructure provisioned in three ordered Terraform roots: bootstrap (state backend), foundation (shared long-lived resources), and platform (compute workloads).

## Quick Reference

### Root Layout

| Root | Directory | State Key | Purpose |
|------|-----------|-----------|---------|
| bootstrap | `bootstrap/` | local (applied once) | Creates the S3 state bucket |
| foundation | `foundation/` | `foundation/terraform.tfstate` | Long-lived shared resources |
| platform | `platform/` | `platform/terraform.tfstate` | Compute resources (EKS, RDS, ALB) |

### Provider Versions

| Tool | Version |
|------|---------|
| Terraform | >= 1.10.0 (CI uses 1.14.3) |
| AWS provider | ~> 6.28.0 |
| Helm provider | ~> 3.1.0 (platform only) |
| Random provider | ~> 3.6.0 |

### AWS Configuration

| Variable | Default |
|----------|---------|
| `aws_region` | `us-east-1` |
| `project_name` | `rideshare` |
| `domain_name` | `ridesharing.portfolio.andresbrocco.com` |
| `vpc_cidr` | `10.0.0.0/16` |
| `availability_zones` | `["us-east-1a", "us-east-1b"]` |
| `github_org` | `andresbrocco` |
| `github_repo` | `rideshare-simulation-platform` |
| `github_branch` | `main` |

### Platform Variables (EKS + RDS)

| Variable | Default (variables.tf) | Prod (platform.tfvars) |
|----------|----------------------|----------------------|
| `cluster_version` | `1.35` | `1.35` |
| `node_instance_type` | `t3.xlarge` | `t3.xlarge` |
| `node_count` | `1` | `3` |
| `node_disk_size` | `50` (GB) | `50` (GB) |
| `postgres_version` | `16.6` | `16.6` |
| `rds_instance_class` | `db.t4g.micro` | `db.t4g.micro` |

> `node_count = 1` in `variables.tf` costs ~$0.31/hr. The `environments/prod/platform.tfvars` overrides to `3` for full-capacity demo runs (~$0.93/hr for nodes alone). Pass `-var node_count=1` to reduce cost.

### AWS Resources Provisioned

#### Foundation (persistent — never destroyed)

| Resource | Name Pattern |
|----------|-------------|
| VPC | `rideshare-vpc` |
| S3 — Bronze | `rideshare-<account-id>-bronze` |
| S3 — Silver | `rideshare-<account-id>-silver` |
| S3 — Gold | `rideshare-<account-id>-gold` |
| S3 — Checkpoints | `rideshare-<account-id>-checkpoints` |
| S3 — Frontend | `rideshare-<account-id>-frontend` |
| S3 — Logs | `rideshare-<account-id>-logs` |
| S3 — Loki | `rideshare-<account-id>-loki` |
| S3 — Tempo | `rideshare-<account-id>-tempo` |
| S3 — Build Assets | `rideshare-<account-id>-build-assets` |
| S3 — TF State | `rideshare-tf-state-<account-id>` |
| ECR | `rideshare/<service>` per service |
| ACM Certificate | `*.ridesharing.portfolio.andresbrocco.com` (us-east-1) |
| CloudFront | Frontend SPA distribution |
| Route 53 Zone | `ridesharing.portfolio.andresbrocco.com` |
| Secrets Manager | `rideshare/api-key`, `rideshare/rds`, `rideshare/data-pipeline`, `rideshare/github-pat` (plus two Lambda-managed hash secrets — not in Terraform state) |
| Glue Databases | `rideshare_bronze`, `rideshare_silver`, `rideshare_gold` |
| Lambda | `rideshare-auth-deploy` |
| KMS CMK | `rideshare-visitor-passwords` (automatic key rotation enabled) |
| DynamoDB | `rideshare-visitors` (PAY_PER_REQUEST, KMS SSE, PITR enabled) |
| SES | Domain identity for `ridesharing.portfolio.andresbrocco.com` with DKIM/SPF/DMARC DNS records |
| IAM Roles | GitHub Actions OIDC, EKS cluster/node, per-workload Pod Identity roles |

#### Platform (ephemeral — destroyed between demo sessions)

| Resource | Name Pattern |
|----------|-------------|
| EKS Cluster | `rideshare-eks` |
| EKS Node Group | `rideshare-node-group` (t3.xlarge, AL2023) |
| RDS PostgreSQL | `rideshare-postgres` (db.t4g.micro, v16.6) |
| ALB Controller | Helm release in `kube-system` |
| External Secrets | Helm release in `external-secrets` |
| DNS (ALB wildcard) | `*.ridesharing.portfolio.andresbrocco.com` |

### Pod Identity Associations (platform/main.tf)

| Service Account | Namespace | IAM Role |
|-----------------|-----------|----------|
| `simulation` | `rideshare-prod` | `simulation_role_arn` |
| `bronze-ingestion` | `rideshare-prod` | `bronze_ingestion_role_arn` |
| `airflow-scheduler` | `rideshare-prod` | `airflow_role_arn` |
| `airflow-webserver` | `rideshare-prod` | `airflow_role_arn` |
| `trino` | `rideshare-prod` | `trino_role_arn` |
| `hive-metastore` | `rideshare-prod` | `hive_metastore_role_arn` |
| `loki` | `rideshare-prod` | `loki_role_arn` |
| `tempo` | `rideshare-prod` | `tempo_role_arn` |
| `external-secrets` | `external-secrets` | `eso_role_arn` |

## Commands

### Bootstrap (one-time, local state)

```bash
cd infrastructure/terraform/bootstrap
aws sts get-caller-identity --profile rideshare   # confirm identity
terraform init
terraform apply --profile rideshare
# Note the output: s3_bucket_name = "rideshare-tf-state-<ACCOUNT_ID>"
```

### Foundation

```bash
cd infrastructure/terraform/foundation
terraform init -backend-config="bucket=rideshare-tf-state-<ACCOUNT_ID>"
terraform plan -var-file=../environments/prod/foundation.tfvars
terraform apply -var-file=../environments/prod/foundation.tfvars
```

### Platform (deploy)

```bash
cd infrastructure/terraform/platform
terraform init -backend-config="bucket=rideshare-tf-state-<ACCOUNT_ID>"
terraform plan -var-file=../environments/prod/platform.tfvars
terraform apply -var-file=../environments/prod/platform.tfvars
```

### Platform (teardown)

```bash
cd infrastructure/terraform/platform
terraform destroy -var-file=../environments/prod/platform.tfvars
```

### Update kubeconfig after platform apply

```bash
# Get cluster name from output
CLUSTER_NAME=$(terraform -chdir=infrastructure/terraform/platform output -raw cluster_name)
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region us-east-1 --profile rideshare
```

### Read a foundation output

```bash
terraform -chdir=infrastructure/terraform/foundation output -raw lambda_auth_deploy_url
terraform -chdir=infrastructure/terraform/foundation output ecr_repository_urls
```

### Create application databases (after platform apply)

After RDS is provisioned, create the `metastore` and `airflow` databases before applying Kubernetes manifests:

```bash
# Get RDS endpoint and credentials
RDS_ENDPOINT=$(terraform -chdir=infrastructure/terraform/platform output -raw rds_endpoint)
POSTGRES_PASSWORD=$(aws secretsmanager get-secret-value \
  --secret-id rideshare/rds --query SecretString --output text | jq -r '.MASTER_PASSWORD')

# Create databases (using a pod in the cluster)
kubectl run rds-init --rm -i --restart=Never --namespace=default \
  --image=postgres:16 --env="PGPASSWORD=${POSTGRES_PASSWORD}" -- \
  psql -h "${RDS_ENDPOINT}" -p 5432 -U postgres -d postgres \
  -c "CREATE DATABASE metastore;" \
  -c "CREATE DATABASE airflow;"
```

## CI/CD Workflows

| Workflow | File | What it does |
|----------|------|-------------|
| Deploy | `.github/workflows/deploy.yml` | Applies platform, resolves K8s placeholders, installs ArgoCD, deploys all services |
| Teardown | `.github/workflows/teardown-platform.yml` | Gracefully stops simulation, destroys platform root, cleans DNS |

The Deploy workflow runs `terraform apply` on the platform root, then pipes outputs (`cluster_name`, `rds_endpoint`) into downstream Kubernetes deployment steps. It also reconciles orphaned EKS addons and Helm releases before planning.

### GitHub Secrets Required

| Secret | Purpose |
|--------|---------|
| `AWS_ACCOUNT_ID` | Used to construct state bucket name and IAM role ARN |
| `GH_DEPLOY_PAT` | GitHub PAT synced to Secrets Manager for Lambda deploy trigger |

## Configuration Files

| File | Purpose |
|------|---------|
| `bootstrap/main.tf` | S3 state bucket with versioning + encryption |
| `foundation/variables.tf` | VPC CIDR, domain, GitHub OIDC config |
| `foundation/backend.tf` | S3 backend (bucket supplied at init time) |
| `platform/variables.tf` | EKS/RDS sizing defaults |
| `platform/backend.tf` | S3 backend (bucket supplied at init time) |
| `platform/data.tf` | Remote state read from foundation |
| `environments/prod/foundation.tfvars` | Production overrides for foundation |
| `environments/prod/platform.tfvars` | Production overrides for platform (node_count=3) |

## Common Tasks

### Reduce running cost to minimum

Edit `environments/prod/platform.tfvars`, set `node_count = 1`, then apply:

```bash
cd infrastructure/terraform/platform
terraform apply -var-file=../environments/prod/platform.tfvars -var node_count=1
```

Or pass the override inline without editing the file.

### Import orphaned EKS addons

The Deploy workflow does this automatically. To do it manually:

```bash
cd infrastructure/terraform/platform
terraform import 'module.eks.aws_eks_addon.ebs_csi' 'rideshare-eks:aws-ebs-csi-driver'
terraform import 'module.eks.aws_eks_addon.coredns' 'rideshare-eks:coredns'
terraform import 'module.eks.aws_eks_addon.kube_proxy' 'rideshare-eks:kube-proxy'
terraform import 'module.eks.aws_eks_addon.vpc_cni' 'rideshare-eks:vpc-cni'
```

### Invalidate CloudFront cache after frontend deploy

```bash
DISTRIBUTION_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='Frontend SPA distribution'].Id" \
  --output text)
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" --paths "/*"
```

### Add a workload Pod Identity role

1. Add an IAM role resource in `foundation/modules/iam/eks_roles.tf` with trust policy for `pods.eks.amazonaws.com`.
2. Export it from `foundation/outputs.tf`.
3. Add an `aws_eks_pod_identity_association` block in `platform/main.tf` referencing the exported ARN.

## Troubleshooting

**`Error: Backend configuration changed` during init**
The S3 bucket name must be supplied at init time — it is not stored in `backend.tf`. Run:
```bash
terraform init -reconfigure -backend-config="bucket=rideshare-tf-state-<ACCOUNT_ID>"
```

**`No valid credential sources found` in CI**
The GitHub Actions workflow requires `id-token: write` permission and the OIDC trust on `rideshare-github-actions` IAM role must match the repo/branch exactly. Verify the role's trust policy `StringLike` condition matches `repo:andresbrocco/rideshare-simulation-platform:ref:refs/heads/main`.

**Foundation plan shows unexpected diff after platform apply**
The foundation `main.tf` creates Glue catalog databases but does not register tables. `platform/data.tf` reads foundation remote state. If foundation's remote state is stale, re-run `terraform apply` on foundation to re-sync.

**EKS nodes not Ready after apply**
The node AMI type is `AL2023_x86_64_STANDARD`. IMDS hop limit is set to 2 to allow pod access through container networking. If nodes are stuck, check node group events:
```bash
kubectl describe nodes
aws eks describe-nodegroup --cluster-name rideshare-eks --nodegroup-name rideshare-node-group
```

**ACM certificate stuck in PENDING_VALIDATION**
The ACM module uses a `us_east_1` provider alias regardless of `aws_region`. DNS validation records are created automatically by the ACM module in the Route 53 zone. If NS delegation has not propagated from the parent zone (`andresbrocco.com`), validation will stall.

**RDS password connection errors**
The RDS master password is generated with `override_special = "!#&*-_=+"` to avoid characters (`%`, `>`, `[`) that break URI and psql parsing. If changing the override, re-generate and update Secrets Manager:
```bash
aws secretsmanager get-secret-value --secret-id rideshare/rds --query SecretString --output text
```

**`terraform destroy` fails on EKS addons**
Remove the addon from state before destroying if it was manually deleted outside Terraform:
```bash
terraform state rm 'module.eks.aws_eks_addon.ebs_csi'
```

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context for three-root deployment model
- [infrastructure/kubernetes](../kubernetes/) — What runs on the EKS cluster
- [services/auth-deploy](../../services/auth-deploy/) — Lambda function source packaged by the foundation root
- [.github/workflows/deploy.yml](../../.github/workflows/deploy.yml) — Full platform deploy pipeline
- [.github/workflows/teardown-platform.yml](../../.github/workflows/teardown-platform.yml) — Platform teardown pipeline
