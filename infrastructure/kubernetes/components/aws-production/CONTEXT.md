# CONTEXT.md — aws-production

## Purpose

A Kustomize `Component` (not an overlay) that bundles all AWS-specific production configuration into a reusable unit. It is consumed by both `overlays/production-duckdb` and `overlays/production-glue` via their `components:` list, avoiding duplication between the two production variants.

## Responsibility Boundaries

- **Owns**: ECR image references and tag placeholders, EKS Pod Identity ServiceAccounts, ExternalSecrets SecretStore pointing to AWS Secrets Manager, ALB Ingress resources for all public-facing services, EBS gp3 StorageClass, Prometheus Kubernetes RBAC, and per-service patches that remove MinIO/LocalStack dependencies
- **Delegates to**: The consuming overlay for any variant-specific configuration (e.g., DuckDB vs Glue catalog selection); Terraform (`infrastructure/terraform/platform/main.tf`) for the actual Pod Identity association between ServiceAccounts and IAM roles
- **Does not handle**: Namespace creation, base manifest definitions, or secrets values (those are fetched at runtime by External Secrets Operator from AWS Secrets Manager)

## Key Concepts

- **Kustomize Component vs Overlay**: This is a `kind: Component` (`apiVersion: kustomize.config.k8s.io/v1alpha1`), not a standard overlay. Components are reusable and composable — multiple overlays can include the same component without forking.
- **EKS Pod Identity**: Workload AWS credentials are delivered via EKS Pod Identity (not IRSA). ServiceAccounts carry no `eks.amazonaws.com/role-arn` annotation; the agent injects credentials at runtime. The Pod Identity associations are defined in Terraform, not here.
- **Image placeholders**: `<account-id>` and `<image-tag>` are literal placeholder strings in ECR image references. The CI/CD deploy workflow replaces them with real values (AWS account ID and git SHA) using `sed` before running `kustomize build`.
- **`imagePullPolicy: IfNotPresent`**: Base manifests use `Never` (for local dev with `kind` or `minikube`). This component patches all affected workloads to `IfNotPresent`, which is correct when images are addressed by immutable git-SHA tags.

## Non-Obvious Details

- **`$patch: delete` is required for boto3 IRSA/Pod Identity fallback**: When MinIO credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_ENDPOINT`) are present in env vars, boto3's credential chain resolves them first and never reaches Pod Identity. Setting these vars to `""` still blocks fallback — they must be deleted entirely using Kustomize's `$patch: delete` directive.
- **SecretStore uses node role, not Pod Identity**: The `aws-secrets-manager` SecretStore authenticates via the EKS node IAM role rather than a Pod Identity association. This is intentional: the Pod Identity webhook may not be running yet during initial cluster bootstrap, so relying on it for secret delivery would create a circular dependency.
- **ALB Ingress group**: All six Ingress resources share `alb.ingress.kubernetes.io/group.name: rideshare`, which causes the AWS Load Balancer Controller to consolidate them into a single ALB with per-host routing rules. This avoids provisioning six separate load balancers.
- **ConfigMap generation with `disableNameSuffixHash`**: The `airflow-init-scripts`, `airflow-dbt-project`, and `airflow-great-expectations` ConfigMaps are generated here (embedding script files and project tarballs) with suffix hashing disabled so ArgoCD can reference them by stable names without needing to track the hash.
- **Kafka EBS patch replaces `emptyDir`**: The base Kafka StatefulSet uses an `emptyDir` volume (data lost on pod restart). This component removes that volume via `$patch: delete` and adds a `volumeClaimTemplate` backed by the `rideshare-storage` EBS StorageClass to provide durable persistence.

## Related Modules

- [infrastructure/kubernetes/components](../CONTEXT.md) — Shares Authentication & Authorization domain (eks pod identity)
- [infrastructure/kubernetes/components](../CONTEXT.md) — Shares AWS Infrastructure & IAM domain (eks pod identity)
- [infrastructure/terraform/foundation/modules/iam](../../../terraform/foundation/modules/iam/CONTEXT.md) — Shares Authentication & Authorization domain (eks pod identity)
- [infrastructure/terraform/foundation/modules/iam](../../../terraform/foundation/modules/iam/CONTEXT.md) — Shares AWS Infrastructure & IAM domain (eks pod identity)
- [infrastructure/terraform/platform/modules/alb](../../../terraform/platform/modules/alb/CONTEXT.md) — Shares Authentication & Authorization domain (eks pod identity)
- [infrastructure/terraform/platform/modules/alb](../../../terraform/platform/modules/alb/CONTEXT.md) — Shares AWS Infrastructure & IAM domain (eks pod identity)
