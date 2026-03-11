# CONTEXT.md — Kubernetes Components

## Purpose

Houses reusable Kustomize `Component` definitions that bundle AWS-production-specific configuration into a single composable unit. Currently contains one component (`aws-production`) that is consumed by multiple overlays (`production-duckdb`, `production-glue`) via `components:` in their kustomization files. This avoids duplicating the same set of AWS patches across every overlay.

## Responsibility Boundaries

- **Owns**: All configuration that is specific to running on AWS EKS (ECR image references, IRSA/Pod Identity ServiceAccounts, ExternalSecrets, ALB Ingress, EBS storage, MinIO-removal patches, production env overrides)
- **Delegates to**: `infrastructure/kubernetes/manifests/` for base resource definitions; `infrastructure/kubernetes/overlays/` for overlay-level composition; `infrastructure/terraform/platform/` for the Pod Identity associations that give these ServiceAccounts their IAM permissions
- **Does not handle**: Overlay-specific divergences (e.g., DuckDB vs Glue catalog selection — those remain in the individual overlays)

## Key Concepts

- **Kustomize Component (`kind: Component`)**: Distinct from an Overlay. A Component is a reusable, composable patch bundle that can be applied by multiple overlays via `components:`. Unlike overlays, Components do not stand alone — they require a parent overlay to be rendered.
- **EKS Pod Identity**: Credential mechanism used instead of IRSA. ServiceAccounts declared in `serviceaccount-irsa-patches.yaml` carry no `eks.amazonaws.com/role-arn` annotation — adding one would re-enable IRSA and break the trust policies. The Pod Identity associations are configured in Terraform.
- **SecretStore bootstrap exception**: `secretstore-aws-patch.yaml` uses node-role credentials (not Pod Identity) to avoid a chicken-and-egg problem during initial cluster bootstrap when the Pod Identity webhook may not yet be available.
- **ALB IngressGroup**: All ingress objects share `alb.ingress.kubernetes.io/group.name: rideshare`, which causes the AWS Load Balancer Controller to consolidate them into a single ALB rather than creating one ALB per Ingress. The `<alb-sg-id>` and `<acm-cert-arn>` placeholders are substituted during the CI deploy workflow.
- **Image placeholder substitution**: ECR image names contain `<account-id>` and `<image-tag>` placeholders that are replaced by the deploy workflow using `kustomize edit set image` before applying.
- **MinIO removal pattern**: Several patches (`trino-patch.yaml`, `loki-patch.yaml`, `loki-config-patch.yaml`, etc.) use `$patch: delete` to remove MinIO-specific initContainers and env vars from base manifests, then substitute AWS S3 via IRSA/Pod Identity credentials.

## Non-Obvious Details

- The `configMapGenerator` embeds `airflow-init-scripts` and pre-built tarballs (`dbt-project.tar.gz`, `ge-project.tar.gz`) so that ArgoCD manages these ConfigMaps as Kustomize resources. The tarballs must be re-generated and committed whenever the DBT project or Great Expectations suite changes.
- `storageclass-ebs.yaml` sets itself as the default StorageClass (`storageclass.kubernetes.io/is-default-class: "true"`), replacing the local-path provisioner default that K3s/kind clusters use. This affects any PVC that does not explicitly name a StorageClass.
- Kafka's base manifest uses `emptyDir` (data lost on pod restart). `kafka-patch.yaml` replaces it with a 10 Gi EBS-backed PVC via `volumeClaimTemplates`, which is irreversible once created — resizing requires manual PVC intervention.
- `simulation-patch.yaml` sets `SIM_SPEED_MULTIPLIER=8` for the production demo to make simulation activity observable in near-real-time, and enables S3 checkpoint save/restore so the simulation state survives pod restarts.

## Related Modules

- [infrastructure/kubernetes/components/aws-production](aws-production/CONTEXT.md) — Shares Authentication & Authorization domain (eks pod identity)
- [infrastructure/kubernetes/components/aws-production](aws-production/CONTEXT.md) — Shares AWS Infrastructure & IAM domain (eks pod identity)
- [infrastructure/terraform/foundation/modules/iam](../../terraform/foundation/modules/iam/CONTEXT.md) — Shares Authentication & Authorization domain (eks pod identity)
- [infrastructure/terraform/foundation/modules/iam](../../terraform/foundation/modules/iam/CONTEXT.md) — Shares AWS Infrastructure & IAM domain (eks pod identity)
- [infrastructure/terraform/platform/modules/alb](../../terraform/platform/modules/alb/CONTEXT.md) — Shares Authentication & Authorization domain (eks pod identity)
- [infrastructure/terraform/platform/modules/alb](../../terraform/platform/modules/alb/CONTEXT.md) — Shares AWS Infrastructure & IAM domain (eks pod identity)
