# CONTEXT.md — Platform Modules

## Purpose

Reusable Terraform modules for the runtime platform layer: EKS cluster provisioning, ALB controller deployment, RDS PostgreSQL, and DNS record guidance. These modules are consumed by `infrastructure/terraform/platform/` and represent the compute and data persistence layer that workloads run on top of.

## Responsibility Boundaries

- **Owns**: EKS cluster lifecycle, managed node group, EKS add-ons, ALB controller Helm release and IAM, RDS instance and credential storage, OIDC provider for IRSA
- **Delegates to**: `infrastructure/terraform/foundation/` for IAM roles, VPC, security groups, and the pre-existing Secrets Manager secret IDs that the RDS module writes into
- **Does not handle**: Kubernetes workload manifests, ArgoCD configuration, application-level secrets, or the actual Route 53 DNS record (see Non-Obvious Details)

## Key Concepts

- **Pod Identity vs IRSA**: All workload IAM roles use EKS Pod Identity (`pods.eks.amazonaws.com` trust principal with `sts:AssumeRole` + `sts:TagSession`). The ALB controller is wired via `aws_eks_pod_identity_association` rather than an IRSA annotation on the ServiceAccount — adding `eks.amazonaws.com/role-arn` would trigger IRSA (`AssumeRoleWithWebIdentity`), which the Pod Identity trust policy does not allow.
- **EBS CSI driver IAM exception**: The EBS CSI add-on uses node role permissions (policy attached in foundation) rather than Pod Identity, because the Pod Identity webhook may not yet be available when the cluster is first created.
- **IMDS hop limit**: The node launch template sets `http_put_response_hop_limit = 2`. EKS pods need hop limit 2 to reach the Instance Metadata Service through container networking. Checkov rule `CKV_AWS_341` is explicitly skipped for this reason.
- **Add-on bootstrap order (two-phase)**: EKS add-ons are installed in two deliberate phases to prevent a deadlock. Phase 1 installs `vpc-cni` and `kube-proxy` directly against the control plane (no `depends_on`) before any nodes exist. Phase 2 boots the node group only after Phase 1 completes (`depends_on` those add-ons), then `coredns`, `aws-ebs-csi-driver`, and `eks-pod-identity-agent` wait on the node group. Without this ordering, nodes stay `NotReady` (no CNI) and the apply deadlocks. `bootstrap_self_managed_addons = false` suppresses EKS auto-installation, making explicit ordering critical.

## Non-Obvious Details

- **DNS module is a no-op**: `modules/dns/` contains only a `null_resource` that prints instructions. The Route 53 ALIAS record for `api.<domain>` cannot be created by Terraform in the same apply because the ALB DNS name is only known after the Kubernetes Ingress resource is applied. A second `terraform apply` or manual record creation is required after the ALB exists.
- **ALB controller Helm chart is inside the EKS module**: The `modules/alb/` module deploys the AWS Load Balancer Controller Helm release and its IAM role. It depends on `var.cluster_name` being passed in, creating an explicit ordering dependency from the `eks` module output to the `alb` module input.
- **RDS password special characters are restricted**: `override_special = "!#&*-_=+"` excludes characters like `%`, `>`, and `[` that would break URI-encoded connection strings and `psql` parsing.
- **Metastore database requires manual creation**: The RDS module creates only the `airflow` database as the initial `db_name`. The `metastore` database (used by Hive Metastore) must be created post-provisioning via psql. The module emits a reminder via a `null_resource` local-exec step.
- **Cluster security group vs custom node SG**: EKS managed nodes receive the EKS-managed cluster security group, not the custom `eks_nodes_sg`. ALB health checks must be permitted on the cluster SG, so the EKS module adds an ingress rule on the cluster SG allowing all TCP from the VPC CIDR.
- **Fixed node count**: The node group sets `desired_size = min_size = max_size = var.node_count`. There is no autoscaling — scale events require a Terraform variable change and re-apply.

## Related Modules

- [infrastructure/terraform/platform](../CONTEXT.md) — Shares Terraform & Infrastructure as Code domain (add-on bootstrap order (two-phase))
- [infrastructure/terraform/platform](../CONTEXT.md) — Shares CI/CD & Deployment Pipeline domain (add-on bootstrap order (two-phase))
- [infrastructure/terraform/platform/modules/eks](eks/CONTEXT.md) — Shares Authentication & Authorization domain (pod identity vs irsa)
