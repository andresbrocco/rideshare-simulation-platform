# CONTEXT.md — Kubernetes Overlays

## Purpose

Environment-specific Kustomize overlays that customize base Kubernetes manifests for different deployment targets. Separates environment concerns (resource limits, storage, networking) from core service definitions.

## Responsibility Boundaries

- **Owns**: Environment-specific configuration (resource limits, replica counts, storage classes, service types, namespaces)
- **Delegates to**: Base manifests in `infrastructure/kubernetes/base/` for core service definitions
- **Does not handle**: Individual service deployment manifests (those live in base/) or cluster provisioning (handled by scripts/ and Terraform)

## Key Concepts

- **Kustomization Overlay Pattern**: Each overlay (local, production) references base manifests and applies environment-specific patches
- **Local Overlay**: Optimized for Kind cluster on developer laptops with minimal resource requirements and NodePort services
- **Production Overlay**: AWS EKS configuration with high availability, LoadBalancer services, and production-grade resource limits

## Non-Obvious Details

The local overlay uses significantly smaller resource limits (500m CPU / 1Gi memory for simulation) compared to production (2 CPU / 4Gi memory). This allows Kind clusters to run on laptops while production maintains performance at scale. Both overlays reference the same base manifests, ensuring configuration consistency across environments.

## Related Modules

- **[infrastructure/kubernetes/manifests](../manifests/CONTEXT.md)** — Provides base manifests that overlays customize for each environment
- **[infrastructure/kubernetes/scripts](../scripts/CONTEXT.md)** — Uses overlays when deploying to different environments via kustomize build
