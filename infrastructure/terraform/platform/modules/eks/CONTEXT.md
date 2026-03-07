# CONTEXT.md — EKS Module

## Purpose

Provisions a production-grade EKS cluster, its managed node group, and all EKS-managed add-ons (CoreDNS, kube-proxy, VPC CNI, EBS CSI driver, Pod Identity agent). Also creates the OIDC identity provider required for IRSA-style trust, even though the platform primarily uses Pod Identity for workload IAM.

## Responsibility Boundaries

- **Owns**: EKS cluster resource, managed node group, launch template, EKS add-ons, OIDC provider, and the ALB-to-cluster-SG ingress rule
- **Delegates to**: `infrastructure/terraform/foundation` modules for all IAM roles (cluster role, node role) and the custom `eks_nodes_sg` security group
- **Does not handle**: Kubernetes manifests, ArgoCD, Helm releases, or application-level IAM Pod Identity associations (those are defined in the platform `main.tf`)

## Key Concepts

- **Pod Identity vs IRSA**: The cluster registers an OIDC provider (normally used for IRSA), but actual workload IAM bindings use EKS Pod Identity associations (defined externally). Both mechanisms coexist; the OIDC provider is retained for potential future use or third-party tooling.
- **EKS-managed cluster SG**: AWS automatically creates a second security group (the cluster SG) and attaches it to all managed nodes alongside the custom `eks_nodes_sg`. This cluster SG is separate from the custom one and is not controlled by Terraform inputs.
- **Fixed-size node group**: `desired_size`, `min_size`, and `max_size` are all set to `var.node_count`. There is no cluster autoscaler — the fleet size is intentionally static to control cost.

## Non-Obvious Details

- **ALB-to-cluster-SG ingress rule**: Because managed nodes only receive the EKS-managed cluster SG (not the custom `eks_nodes_sg`), ALB health checks cannot reach pods through the custom SG alone. A separate `aws_vpc_security_group_ingress_rule` opens all TCP ports from the VPC CIDR on the cluster SG to compensate. This rule targets the cluster SG ID exposed via `vpc_config[0].cluster_security_group_id`.
- **IMDS hop limit of 2**: The launch template sets `http_put_response_hop_limit = 2` (not the IMDSv2-hardened default of 1) because containers inside pods need two network hops to reach the instance metadata service. A Checkov rule (`CKV_AWS_341`) is explicitly skipped with this justification.
- **EBS CSI driver uses node role, not Pod Identity**: The `aws-ebs-csi-driver` add-on inherits permissions from the node IAM role (`AmazonEBSCSIDriverPolicy` attached in foundation) rather than using a Pod Identity association. This is intentional: the Pod Identity webhook may not be available during the first `terraform apply`, and node-role permissions are sufficient for this add-on's access pattern.
- **Authentication mode `API_AND_CONFIG_MAP`**: The cluster uses both the EKS Access API and the legacy `aws-auth` ConfigMap. This allows bootstrap-creator admin access (needed for CI/CD) while remaining compatible with tools that still rely on the ConfigMap.
- **Add-on bootstrap order**: All four add-ons depend on `aws_eks_node_group.main`, and the Pod Identity agent add-on additionally depends on the node group being ready before it is installed. This ordering prevents add-on activation before worker nodes exist.

## Related Modules

- [infrastructure/terraform/foundation/modules](../../../foundation/modules/CONTEXT.md) — Shares AWS IAM and Security domain (pod identity)
- [infrastructure/terraform/platform](../../CONTEXT.md) — Shares AWS IAM and Security domain (imds hop limit)
- [infrastructure/terraform/platform](../../CONTEXT.md) — Shares EKS Cluster Configuration domain (imds hop limit)
- [infrastructure/terraform/platform/modules](../CONTEXT.md) — Shares AWS IAM and Security domain (irsa, pod identity)
