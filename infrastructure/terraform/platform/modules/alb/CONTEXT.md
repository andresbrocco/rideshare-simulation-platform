# CONTEXT.md — ALB

## Purpose

Deploys the AWS Load Balancer Controller into the EKS cluster via Helm, provisions the IAM role it needs (using EKS Pod Identity), and co-locates installation of two unrelated cluster-wide Helm charts (External Secrets Operator and kube-state-metrics) that depend on the ALB controller webhook being ready first.

## Responsibility Boundaries

- **Owns**: AWS Load Balancer Controller Helm release, its IAM role and inline policy, the Pod Identity association binding that role to the controller's ServiceAccount
- **Delegates to**: `platform` root module for the EKS cluster and VPC details passed in as variables; ArgoCD / application manifests for actually creating `Ingress` resources that the controller reconciles
- **Does not handle**: TLS certificate provisioning (see `acm` module), DNS records (see `dns` module), or application-level Ingress definitions

## Key Concepts

- **EKS Pod Identity**: The mechanism used to inject AWS credentials into the ALB controller pod. The IAM role's trust policy grants `pods.eks.amazonaws.com` permission to `sts:AssumeRole` and `sts:TagSession`. An `aws_eks_pod_identity_association` resource binds the role to the `aws-load-balancer-controller` ServiceAccount in `kube-system` after the Helm release exists.

## Non-Obvious Details

- **Do not add the IRSA annotation to the ServiceAccount.** The Helm `set` block intentionally omits `serviceAccount.annotations."eks.amazonaws.com/role-arn"`. Adding it would activate IRSA (`AssumeRoleWithWebIdentity`), which the trust policy does not permit, causing credential failures. Pod Identity injects credentials automatically without an annotation.
- **Pod Identity association is created after the Helm release** (`depends_on = [helm_release.aws_load_balancer_controller]`). This ordering is required because the ServiceAccount must exist in the cluster before EKS can create the association.
- **Scope creep by design**: External Secrets Operator and kube-state-metrics are installed here solely because they need the ALB controller webhook to be available before their own Services are created. This is a dependency-ordering convenience, not a conceptual grouping.
- **IAM policy is sourced from the official upstream policy document** (`kubernetes-sigs/aws-load-balancer-controller` repo). The inline policy is verbose but intentional — it mirrors the official recommended permissions exactly.

## Related Modules

- [infrastructure/kubernetes/components](../../../../kubernetes/components/CONTEXT.md) — Shares AWS IAM and Security domain (eks pod identity)
- [infrastructure/kubernetes/components/aws-production](../../../../kubernetes/components/aws-production/CONTEXT.md) — Shares AWS IAM and Security domain (eks pod identity)
- [infrastructure/terraform/foundation/modules/iam](../../../foundation/modules/iam/CONTEXT.md) — Shares AWS IAM and Security domain (eks pod identity)
- [infrastructure/terraform/platform](../../CONTEXT.md) — Shares AWS IAM and Security domain (eks pod identity)
- [infrastructure/terraform/platform/modules](../CONTEXT.md) — Shares Kubernetes and ArgoCD Deployment domain (aws load balancer controller)
