# Cloud Deployment Guide

> Deploy the rideshare simulation platform to AWS at `ridesharing.portfolio.andresbrocco.com`

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Bootstrap: Terraform State Backend](#bootstrap-terraform-state-backend)
4. [Foundation: Always-On Infrastructure](#foundation-always-on-infrastructure)
5. [DNS Delegation](#dns-delegation)
6. [Frontend Deployment](#frontend-deployment)
7. [Platform Deployment](#platform-deployment)
8. [Verification](#verification)
9. [Teardown](#teardown)
10. [Cost Reference](#cost-reference)
11. [Service Access URLs](#service-access-urls)
12. [Troubleshooting](#troubleshooting)

## Architecture Overview

The deployment is split into two layers:

- **Foundation** (always deployed, ~$7.50/mo): Networking, DNS, CDN, storage, container registry, secrets, IAM. React frontend is always accessible as a static site.
- **Platform** (on-demand, ~$0.65/hr): EKS cluster, worker nodes, RDS, ALB. Created for demos, destroyed afterward.

When the platform is down, the frontend detects API unreachability and displays a graceful "demo offline" state. When up, the frontend connects to the full interactive backend.

```
                    ┌─────────────────────────────────────────────┐
                    │           Foundation (~$7.50/mo)            │
                    │                                             │
  Browser ───────── │  CloudFront ── S3 (React SPA)              │
                    │  Route 53 (DNS)                             │
                    │  ACM (TLS wildcard cert)                    │
                    │  ECR (container images)                     │
                    │  Secrets Manager (credentials)              │
                    │  VPC + Subnets + Security Groups            │
                    └─────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────┐
                    │           Platform (~$0.65/hr)              │
                    │                                             │
  Browser ───────── │  ALB ── EKS Cluster (3x t3.xlarge)         │
                    │         ├── Simulation + Stream Processor   │
                    │         ├── Kafka + Redis + OSRM            │
                    │         ├── Airflow + Trino + Hive          │
                    │         ├── Grafana + Prometheus + Loki     │
                    │         └── ArgoCD (GitOps)                 │
                    │  RDS PostgreSQL (Airflow + Hive metadata)   │
                    └─────────────────────────────────────────────┘
```

## Prerequisites

### AWS Account

- AWS account with billing configured
- IAM user with AdministratorAccess or equivalent permissions
- AWS CLI installed and configured: `aws configure`

### Domain

- Domain ownership for `andresbrocco.com` (or subdomain already delegated to Route 53)
- Access to domain registrar to add NS records

### GitHub Repository

- Repository at `andresbrocco/rideshare-simulation-platform`
- GitHub Actions enabled
- AWS OIDC provider configured (created automatically by foundation Terraform — no manual setup needed). After applying foundation, verify with:

  ```bash
  aws iam list-open-id-connect-providers --profile rideshare
  # Should show a provider with "token.actions.githubusercontent.com" in the ARN
  ```

- Repository secret: `AWS_ACCOUNT_ID` (12-digit AWS account ID). Find your account ID and set the secret:

  ```bash
  # Get your AWS account ID
  aws sts get-caller-identity --profile rideshare --query Account --output text

  # Set the GitHub Actions secret
  gh secret set AWS_ACCOUNT_ID --repo andresbrocco/rideshare-simulation-platform
  # Paste your 12-digit account ID when prompted

  # Verify it was set
  gh secret list --repo andresbrocco/rideshare-simulation-platform
  ```

### Local Tools

| Tool | Version | Install |
|------|---------|---------|
| Terraform | 1.14.3+ | `brew install hashicorp/tap/terraform` |
| AWS CLI | 2.x | `brew install awscli` |
| kubectl | 1.31+ | `brew install kubectl` |
| helm | 4.0+ | `brew install helm` |
| Git + LFS | latest | `brew install git git-lfs` |

Verify installations:

```bash
terraform version    # >= 1.14.3
aws --version        # >= 2.x
kubectl version      # >= 1.31
helm version         # >= 4.0
git lfs version      # any
```

## Bootstrap: Terraform State Backend

**Purpose:** One-time manual setup to create S3 bucket and DynamoDB table for Terraform state management.

**Duration:** ~2 minutes

**Steps:**

```bash
# Navigate to bootstrap directory
cd infrastructure/terraform/bootstrap

# Initialize Terraform (local state)
terraform init

# Review plan
terraform plan

# Apply (creates rideshare-tf-state bucket and DynamoDB lock table)
terraform apply
```

**Verify:**

```bash
aws s3 ls | grep rideshare-tf-state
aws dynamodb list-tables | grep terraform-lock
```

**Outputs:**

| Resource | Name |
|----------|------|
| S3 bucket | `rideshare-tf-state` |
| DynamoDB table | `terraform-lock` |

**Important:**

- Bootstrap uses local state (not remote backend)
- Only run once per AWS account
- Do NOT destroy this infrastructure (or you lose all Terraform state)

## Foundation: Always-On Infrastructure

**Purpose:** Deploy always-on infrastructure (~$7.50/mo): VPC, S3, CloudFront, Route 53, ACM, ECR, Secrets Manager, IAM.

**Duration:** ~5-7 minutes (ACM certificate validation may take up to 5 min)

**Steps:**

```bash
# Navigate to foundation directory
cd infrastructure/terraform/foundation

# Initialize Terraform (remote S3 backend)
terraform init

# Review plan
terraform plan

# Apply
terraform apply
```

**Expected Outputs:**

| Output | Description | Example Value |
|--------|-------------|---------------|
| `vpc_id` | VPC identifier | `vpc-0a1b2c3d4e5f6g7h8` |
| `subnet_ids` | Public subnet IDs | `["subnet-abc123", "subnet-def456"]` |
| `route53_zone_id` | Hosted zone ID | `Z1234567890ABC` |
| `route53_nameservers` | NS records for delegation | `["ns-123.awsdns-12.com", ...]` |
| `acm_certificate_arn` | Wildcard TLS cert ARN | `arn:aws:acm:us-east-1:...` |
| `cloudfront_distribution_id` | CDN distribution ID | `E1A2B3C4D5E6F7` |
| `cloudfront_domain_name` | CloudFront domain | `d111111abcdef8.cloudfront.net` |
| `ecr_repository_urls` | Container registry URLs | `{"simulation": "123456789012.dkr.ecr..."}` |
| `s3_bucket_names` | Lakehouse bucket names | `{"bronze": "rideshare-bronze", ...}` |
| `github_actions_role_arn` | CI/CD IAM role ARN | `arn:aws:iam::123456789012:role/rideshare-github-actions` |

**Verify:**

```bash
# Check VPC
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=rideshare-vpc"

# Check S3 buckets
aws s3 ls | grep rideshare

# Check CloudFront distribution
aws cloudfront list-distributions \
  --query 'DistributionList.Items[?Comment==`Frontend SPA distribution`].DomainName'

# Check ECR repositories
aws ecr describe-repositories \
  --query 'repositories[?contains(repositoryName, `rideshare`)].repositoryName'

# Check Secrets Manager
aws secretsmanager list-secrets \
  --query 'SecretList[?contains(Name, `rideshare`)].Name'
```

## DNS Delegation

**Purpose:** Delegate `ridesharing.portfolio.andresbrocco.com` from your domain registrar to Route 53.

**Duration:** ~5-10 minutes (DNS propagation)

### Step 1: Get Route 53 Name Servers

```bash
cd infrastructure/terraform/foundation
terraform output route53_nameservers
```

Example output:

```
[
  "ns-123.awsdns-12.com",
  "ns-456.awsdns-45.org",
  "ns-789.awsdns-78.net",
  "ns-012.awsdns-01.co.uk"
]
```

### Step 2: Add NS Records in Domain Registrar

Log in to your domain registrar (e.g., Namecheap, GoDaddy, Route 53 for parent domain) and add NS records:

| Record Type | Name | Value |
|-------------|------|-------|
| NS | `ridesharing.portfolio.andresbrocco.com` | `ns-123.awsdns-12.com` |
| NS | `ridesharing.portfolio.andresbrocco.com` | `ns-456.awsdns-45.org` |
| NS | `ridesharing.portfolio.andresbrocco.com` | `ns-789.awsdns-78.net` |
| NS | `ridesharing.portfolio.andresbrocco.com` | `ns-012.awsdns-01.co.uk` |

If `andresbrocco.com` is already managed in Route 53, add NS records in the parent hosted zone instead of at the registrar level.

### Step 3: Verify DNS Delegation

```bash
# Check NS records (should show Route 53 name servers)
dig NS ridesharing.portfolio.andresbrocco.com

# Check apex A record (should show CloudFront distribution)
dig ridesharing.portfolio.andresbrocco.com

# Use Google DNS to bypass local cache
dig @8.8.8.8 NS ridesharing.portfolio.andresbrocco.com

# Verify HTTPS access to frontend (should serve React app in offline mode)
curl -I https://ridesharing.portfolio.andresbrocco.com
```

Expected results:

- NS query: Returns Route 53 name servers
- A query: Returns CloudFront IP addresses
- HTTPS: Returns `200 OK` with `Content-Type: text/html`

## Frontend Deployment

**Purpose:** Deploy React static site to S3 and CloudFront.

**Duration:** ~2-3 minutes

### Option 1: GitHub Actions (Recommended)

Trigger the `deploy-frontend.yml` workflow:

```
GitHub Actions -> deploy-frontend.yml -> Run workflow
```

Or push changes to `services/frontend/**` to trigger automatically:

```bash
git add services/frontend
git commit -m "Update frontend"
git push origin main
```

### Option 2: Manual Deployment

```bash
# Build frontend with production env vars
cd services/frontend
VITE_API_URL=https://api.ridesharing.portfolio.andresbrocco.com \
VITE_WS_URL=wss://api.ridesharing.portfolio.andresbrocco.com/ws \
npm run build

# Sync to S3 (replace bucket name from Terraform output)
aws s3 sync dist/ s3://rideshare-frontend --delete

# Invalidate CloudFront cache (replace distribution ID from Terraform output)
aws cloudfront create-invalidation \
  --distribution-id E1A2B3C4D5E6F7 \
  --paths "/*"
```

**Verify:**

```bash
# Visit frontend (should show offline mode when platform is down)
open https://ridesharing.portfolio.andresbrocco.com
```

## Platform Deployment

**Purpose:** Deploy on-demand infrastructure (~$0.65/hr): EKS cluster, RDS, ALB.

**Duration:** ~15-20 minutes (EKS creation: ~10 min, service startup: ~5 min)

### GitHub Actions (Recommended)

```
GitHub Actions -> Deploy Platform to AWS -> Run workflow
# Input confirmation: "deploy"
```

**What the workflow does:**

1. Configures AWS credentials via OIDC
2. Runs `terraform apply` in `infrastructure/terraform/platform`
3. Creates EKS cluster (v1.31), RDS PostgreSQL, ALB
4. Updates kubeconfig with EKS cluster
5. Installs ArgoCD on cluster
6. Applies ArgoCD Application manifests
7. Waits for pods to reach Ready state
8. Runs health checks
9. Outputs deployment summary with service URLs

### Manual Deployment (Advanced)

```bash
cd infrastructure/terraform/platform

# Initialize and apply
terraform init
terraform apply

# Update kubeconfig
aws eks update-kubeconfig --name rideshare-prod --region us-east-1

# Install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.2.3/manifests/install.yaml

# Wait for ArgoCD server
kubectl wait --for=condition=available --timeout=300s \
  deployment/argocd-server -n argocd

# Apply ArgoCD applications
kubectl apply -f infrastructure/kubernetes/argocd/app-core-services.yaml
kubectl apply -f infrastructure/kubernetes/argocd/app-data-pipeline.yaml
```

## Verification

### Health Checks

```bash
# Check EKS cluster
aws eks describe-cluster --name rideshare-prod --query 'cluster.status'

# Check RDS instance
aws rds describe-db-instances \
  --query 'DBInstances[?contains(DBInstanceIdentifier, `rideshare`)].Endpoint.Address'

# Check ALB
aws elbv2 describe-load-balancers \
  --query 'LoadBalancers[?contains(LoadBalancerName, `rideshare`)].DNSName'

# Check pods
kubectl get pods -n rideshare-prod

# Check ArgoCD applications
kubectl get applications -n argocd
```

### Smoke Test

```bash
# Test API health
curl https://api.ridesharing.portfolio.andresbrocco.com/api/health

# Start simulation
curl -X POST -H "X-API-Key: admin" \
  https://api.ridesharing.portfolio.andresbrocco.com/api/simulation/start

# Spawn drivers
curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 10}' \
  https://api.ridesharing.portfolio.andresbrocco.com/api/agents/drivers

# Spawn riders
curl -X POST -H "X-API-Key: admin" \
  -H "Content-Type: application/json" \
  -d '{"count": 20}' \
  https://api.ridesharing.portfolio.andresbrocco.com/api/agents/riders

# Check frontend (should show live simulation)
open https://ridesharing.portfolio.andresbrocco.com
```

## Teardown

**Purpose:** Destroy on-demand infrastructure to reduce cost to ~$7.50/mo.

**Duration:** ~10-15 minutes

### GitHub Actions (Recommended)

```
GitHub Actions -> Teardown Platform from AWS -> Run workflow
# Input confirmation: "teardown"
```

**What the workflow does:**

1. Configures AWS credentials via OIDC
2. Runs `terraform destroy` in `infrastructure/terraform/platform`
3. Destroys EKS cluster, RDS, ALB, EBS volumes
4. Removes `api.*` Route 53 record
5. Verifies foundation resources preserved
6. Outputs teardown summary

### What is Destroyed

- EKS cluster (rideshare-prod)
- EC2 instances (3x t3.xlarge worker nodes)
- RDS PostgreSQL (t4g.micro)
- ALB (Application Load Balancer)
- EBS volumes (Kafka data, Prometheus TSDB)
- Route 53 `api.*` record

### What is Preserved

- S3 buckets (lakehouse data: bronze, silver, gold; simulation checkpoints [save-only; restore not yet implemented]; frontend build)
- ECR images (all 7 service images)
- Secrets Manager (all 12 secret groups)
- Route 53 hosted zone (ridesharing.portfolio.andresbrocco.com)
- CloudFront distribution
- ACM wildcard certificate
- VPC, subnets, security groups, IAM roles

### Verify Teardown

```bash
# Frontend should show offline mode
open https://ridesharing.portfolio.andresbrocco.com

# API should be unreachable
curl https://api.ridesharing.portfolio.andresbrocco.com/api/health
# Expected: Connection timeout or DNS resolution failure

# S3 buckets should still exist
aws s3 ls | grep rideshare

# ECR images should still exist
aws ecr describe-repositories \
  --query 'repositories[?contains(repositoryName, `rideshare`)].repositoryName'
```

## Cost Reference

### Foundation (Always-On)

| Resource | Monthly Cost |
|----------|-------------|
| Route 53 hosted zone | $0.50 |
| CloudFront (low traffic) | ~$1.00 |
| S3 (frontend + lakehouse, <10 GB) | ~$0.50 |
| ECR (7 repos, ~5 GB total) | ~$0.50 |
| Secrets Manager (12 secrets) | $4.80 |
| DynamoDB (Terraform lock, on-demand) | ~$0.10 |
| VPC, subnets, security groups | $0.00 |
| ACM certificate | $0.00 |
| **Foundation Total** | **~$7.50/mo** |

### Platform (On-Demand)

| Resource | Hourly Cost |
|----------|------------|
| EKS control plane | $0.10 |
| 3x t3.xlarge (on-demand) | $0.50 |
| ALB | $0.025 |
| RDS t4g.micro | $0.016 |
| EBS (~100 GB gp3) | ~$0.011 |
| **Platform Total** | **~$0.65/hr** |

### Monthly Estimates by Usage

| Scenario | Monthly Cost |
|----------|-------------|
| Foundation only (no demos) | ~$8 |
| 1 demo/week (4 hrs each) | ~$8 + $10 = **~$18** |
| 4 demos/week (4 hrs each) | ~$8 + $42 = **~$50** |
| Always-on (730 hrs) | ~$8 + $475 = **~$483** |

### Cost Optimization Tips

- Destroy platform immediately after demos
- Use `terraform destroy` or the teardown workflow to clean up
- Monitor AWS Cost Explorer for unexpected charges
- Set up billing alerts at $50 and $100 thresholds
- Check for orphaned resources (ALBs, EBS volumes) after teardown

## Service Access URLs

### Frontend (Always Available)

| URL | Description |
|-----|-------------|
| https://ridesharing.portfolio.andresbrocco.com | React control panel (offline mode when platform down) |

### API (Platform Running Only)

All `/api/*` paths require `X-API-Key: admin` header.

| URL | Description |
|-----|-------------|
| https://api.ridesharing.portfolio.andresbrocco.com/api/health | Simulation health check |
| https://api.ridesharing.portfolio.andresbrocco.com/api/simulation/status | Simulation status |
| https://api.ridesharing.portfolio.andresbrocco.com/api/agents/drivers | Create drivers |
| https://api.ridesharing.portfolio.andresbrocco.com/api/agents/riders | Create riders |
| https://api.ridesharing.portfolio.andresbrocco.com/ws | WebSocket for real-time updates |

### Dashboards (Platform Running Only)

| URL | Credentials | Description |
|-----|-------------|-------------|
| https://api.ridesharing.portfolio.andresbrocco.com/grafana/ | admin / admin | Multi-datasource dashboards |
| https://api.ridesharing.portfolio.andresbrocco.com/airflow/ | admin / admin | Pipeline orchestration |
| https://api.ridesharing.portfolio.andresbrocco.com/trino/ | - | SQL query engine |

Grafana and Airflow credentials are stored in Secrets Manager. Trino is accessible via JDBC/HTTP at port 8080.

## Troubleshooting

### DNS Delegation Not Working

**Symptom:** `dig NS ridesharing.portfolio.andresbrocco.com` does not return Route 53 name servers.

**Solutions:**

1. Verify NS records added correctly in domain registrar
2. Wait 5-10 minutes for DNS propagation
3. Check parent domain NS records: `dig NS andresbrocco.com`
4. Use Google DNS for testing: `dig @8.8.8.8 NS ridesharing.portfolio.andresbrocco.com`

### ACM Certificate Validation Stuck

**Symptom:** Foundation Terraform times out during ACM certificate creation.

**Solutions:**

1. Verify DNS delegation completed first (ACM needs DNS for validation)
2. Check Route 53 records for `_acm-challenge.*` CNAME
3. Wait up to 30 minutes for validation
4. Re-run `terraform apply` (idempotent)

### EKS Cluster Creation Timeout

**Symptom:** Deploy workflow times out after 45 minutes.

**Solutions:**

1. Check AWS console for cluster status
2. Re-run deploy workflow (Terraform resumes from last state)
3. Verify VPC subnets have available IPs
4. Check IAM role permissions

### ArgoCD Applications Not Syncing

**Symptom:** Pods not appearing in rideshare-prod namespace.

**Solutions:**

1. Check ArgoCD UI: `kubectl port-forward svc/argocd-server -n argocd 8080:443`
2. Get admin password: `kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d`
3. Manually sync: `argocd app sync app-core-services`
4. Check application events: `kubectl describe application app-core-services -n argocd`

### Frontend Shows Offline Mode Despite Platform Running

**Symptom:** Frontend displays "demo offline" even though EKS is running.

**Solutions:**

1. Check API health: `curl https://api.ridesharing.portfolio.andresbrocco.com/api/health`
2. Verify ALB provisioned: `kubectl get ingress rideshare-ingress -n rideshare-prod`
3. Check Route 53 `api.*` record points to ALB
4. Wait 2-3 minutes for DNS propagation after deployment
5. Clear browser cache and reload

### Terraform State Lock Error

**Symptom:** `terraform apply` fails with "state locked" error.

**Solutions:**

1. Check for other running Terraform processes
2. Force unlock (use with caution): `terraform force-unlock <LOCK_ID>`
3. Verify DynamoDB table exists: `aws dynamodb describe-table --table-name terraform-lock`

### High AWS Costs

**Symptom:** Monthly bill higher than expected.

**Solutions:**

1. Verify platform destroyed: `aws eks list-clusters`
2. Check for orphaned ALBs: `aws elbv2 describe-load-balancers`
3. Check EBS volumes: `aws ec2 describe-volumes --query 'Volumes[?State==`available`]'`
4. Review CloudWatch logs retention (may incur costs)
5. Set up billing alerts for early detection

## Related Documentation

- [README.md](../README.md) - Local development setup
- [docs/INFRASTRUCTURE.md](INFRASTRUCTURE.md) - Docker and Kubernetes infrastructure
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) - System design and event flow
- [GitHub Actions Workflows](../.github/workflows/) - CI/CD pipeline definitions
