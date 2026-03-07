# CONTEXT.md — Platform

## Purpose

Provisions the runtime infrastructure layer on top of the foundation layer. This includes the EKS cluster with its managed node group, RDS PostgreSQL instance, ALB ingress controller, External Secrets Operator, DNS setup, and all EKS Pod Identity associations that grant workload-specific IAM roles to Kubernetes service accounts.

## Responsibility Boundaries

- **Owns**: EKS cluster and node group, RDS instance, ALB controller Helm install, External Secrets Operator Helm install, kube-state-metrics Helm install, Pod Identity associations for all workloads, Route 53 DNS placeholder
- **Delegates to**: `infrastructure/terraform/foundation` — VPC, subnets, security groups, IAM roles, and the RDS Secrets Manager secret are all consumed via `terraform_remote_state`
- **Does not handle**: Kubernetes application manifests, ArgoCD, Kafka, Airflow DAGs, or any application-level configuration; those are managed in `infrastructure/kubernetes`

## Key Concepts

- **Two-layer Terraform split**: Foundation creates the IAM roles and networking; Platform consumes foundation outputs via `terraform_remote_state` and wires them together into a running cluster. Changes to IAM or VPC require a `foundation` apply before a `platform` apply.
- **EKS Pod Identity (not IRSA)**: All workload IAM role bindings use `aws_eks_pod_identity_association` resources, which rely on the `eks-pod-identity-agent` addon rather than OIDC/IRSA annotations on ServiceAccounts. Adding an `eks.amazonaws.com/role-arn` annotation to a ServiceAccount would trigger IRSA instead and fail because the trust policy only allows `pods.eks.amazonaws.com`.
- **ALB controller credential constraint**: The ALB controller Helm chart must not receive an IRSA role-ARN annotation; its credentials come exclusively from Pod Identity. This is noted in an inline comment in `alb/main.tf`.
- **IMDS hop limit 2**: The EKS node launch template sets `http_put_response_hop_limit = 2` to allow pods inside containers to reach IMDS and receive Pod Identity credentials. The Checkov rule `CKV_AWS_341` is intentionally skipped for this reason.

## Non-Obvious Details

- **Backend bucket injected at init time**: `backend.tf` leaves the S3 bucket name unset and requires `-backend-config="bucket=rideshare-tf-state-<ACCOUNT_ID>"` at `terraform init`. The bucket name is account-specific and cannot be hardcoded.
- **RDS password special characters**: The `random_password` for RDS uses `override_special = "!#&*-_=+"` to exclude characters (`%`, `>`, `[`) that break URI parsing and `psql` connection strings.
- **`metastore` database not auto-created**: RDS is initialized with a single `airflow` database. The `metastore` database must be created manually via `psql` after RDS is provisioned — `rds/main.tf` emits instructions via a `null_resource` local-exec.
- **DNS is a placeholder**: The `dns` module emits instructions rather than creating an actual Route 53 record, because the ALB DNS name is not known until the Kubernetes Ingress resource is applied. The ALIAS record must be created in a second step after ArgoCD deploys the Ingress.
- **EBS CSI driver uses node role, not Pod Identity**: The EBS CSI addon intentionally does not use Pod Identity because the Pod Identity webhook may not be ready during initial cluster bootstrapping. The node role has `AmazonEBSCSIDriverPolicy` attached in the foundation layer instead.
- **Access entry for deploy user**: A non-GitHub CI user (`rideshare-deploy` IAM user) is granted `AmazonEKSClusterAdminPolicy` via an access entry so local `kubectl` operations work. The GitHub Actions role gets admin automatically via `bootstrap_cluster_creator_admin_permissions = true`.

## Related Modules

- [infrastructure/kubernetes/components](../../kubernetes/components/CONTEXT.md) — Reverse dependency — Provides aws-production component (kustomization.yaml)
- [infrastructure/kubernetes/components](../../kubernetes/components/CONTEXT.md) — Shares AWS IAM and Security domain (eks pod identity)
- [infrastructure/kubernetes/components/aws-production](../../kubernetes/components/aws-production/CONTEXT.md) — Shares AWS IAM and Security domain (eks pod identity)
- [infrastructure/terraform/environments](../environments/CONTEXT.md) — Reverse dependency — Consumed by this module
- [infrastructure/terraform/foundation](../foundation/CONTEXT.md) — Dependency — Provisions long-lived AWS infrastructure that must exist before the EKS cluster ...
- [infrastructure/terraform/foundation](../foundation/CONTEXT.md) — Shares Terraform Infrastructure as Code domain (two-layer terraform split (foundation vs platform))
- [infrastructure/terraform/foundation/modules/iam](../foundation/modules/iam/CONTEXT.md) — Shares AWS IAM and Security domain (eks pod identity)
- [infrastructure/terraform/platform/modules/alb](modules/alb/CONTEXT.md) — Shares AWS IAM and Security domain (eks pod identity)
- [infrastructure/terraform/platform/modules/eks](modules/eks/CONTEXT.md) — Shares AWS IAM and Security domain (imds hop limit)
- [infrastructure/terraform/platform/modules/eks](modules/eks/CONTEXT.md) — Shares EKS Cluster Configuration domain (imds hop limit)
