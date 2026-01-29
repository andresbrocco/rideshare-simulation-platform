# CONTEXT.md — Kubernetes Manifests

## Purpose

Kubernetes resource definitions for deploying the rideshare simulation platform to a local Kind cluster. Contains declarative YAML manifests for all services, infrastructure components, networking, storage, and configuration management.

## Responsibility Boundaries

- **Owns**: Kubernetes resource definitions (Deployments, StatefulSets, Services, PVCs, ConfigMaps, Secrets, Gateway/HTTPRoutes)
- **Delegates to**: Lifecycle scripts (`infrastructure/kubernetes/scripts/`) for cluster creation, deployment orchestration, and teardown
- **Does not handle**: Cluster provisioning (handled by Kind cluster config), runtime configuration changes (use `kubectl apply`), or cloud provider resources (handled by Terraform)

## Key Concepts

**Service Categories**: Manifests are organized by service name, not by resource type. Each service typically includes multiple resources (Deployment/StatefulSet + Service + optional PVC).

**Gateway API**: Uses Kubernetes Gateway API (not Ingress) for HTTP routing. The `gateway.yaml` defines the entry point, while `httproute-*.yaml` files define path-based routing rules with URL rewriting.

**StatefulSet vs Deployment**: Kafka uses StatefulSet for stable network identity and persistent storage. Most other services use Deployments as they are either stateless or use separate PVCs.

**Configuration Strategy**: Two-tier configuration with ConfigMaps for non-sensitive values (`configmap-core.yaml`, `configmap-data-pipeline.yaml`) and Secrets for credentials (`secret-credentials.yaml`, `secret-api-keys.yaml`). Services load configuration via `envFrom` or individual `valueFrom` references.

**Storage Model**: Uses Kind's local-path-provisioner with `Delete` reclaim policy. PVCs are pre-created for stateful services (MinIO, PostgreSQL instances, Kafka). Critical data must be backed up before PVC deletion as volumes are automatically destroyed.

**Init Containers**: Services with dependencies use init containers to wait for upstream services (e.g., simulation waits for Kafka, Redis, OSRM, Schema Registry, Stream Processor). This ensures correct startup ordering without external orchestration.

## Non-Obvious Details

**Image Pull Policy**: Uses `imagePullPolicy: Never` for custom images (simulation, stream-processor, frontend) as these are built locally and loaded into Kind with `kind load docker-image`.

**Kafka Listener Configuration**: Kafka exposes three ports: 9092 (external), 29092 (internal cluster communication), 29093 (KRaft controller). Internal services connect via `kafka-0.kafka.default.svc.cluster.local:29092`.

**Headless Service Pattern**: Kafka uses a headless service (`clusterIP: None`) to enable direct pod-to-pod communication and stable DNS names for StatefulSet pods.

**Gateway HTTPRoute Ordering**: HTTPRoute rules are evaluated in order. The frontend route (`/`) must be defined last as it matches all paths. More specific routes (e.g., `/api/`) must come first.

**Existing Documentation**: `README-CONFIG.md` explains ConfigMap/Secret usage patterns. `BACKUP_RESTORE.md` provides operational procedures for stateful data. Both should be verified against actual manifests as they may become outdated.

## Related Modules

- **[infrastructure/kubernetes/scripts](../scripts/CONTEXT.md)** — Uses these manifests to orchestrate deployment with dependency-aware ordering
- **[infrastructure/kubernetes/overlays](../overlays/CONTEXT.md)** — Applies environment-specific patches to these base manifests via Kustomize
