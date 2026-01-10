# Core Services - Kubernetes Manifests

Base Kubernetes manifests for core simulation services.

## Services Included

- **simulation**: FastAPI + SimPy engine
- **stream-processor**: Kafka -> Redis bridge
- **frontend**: React control panel
- **kafka**: Kafka broker (KRaft mode)
- **redis**: Redis for state snapshots and pub/sub
- **osrm**: Routing service for Sao Paulo

## Usage

These base manifests are meant to be used with overlays (local or production).

```bash
# Apply with local overlay
kubectl apply -k ../../overlays/local

# Apply with production overlay
kubectl apply -k ../../overlays/production
```

## Manifest Files (to be added in Phase 6)

- `simulation-deployment.yaml` - Simulation service deployment
- `stream-processor-deployment.yaml` - Stream processor deployment
- `frontend-deployment.yaml` - Frontend deployment
- `kafka-statefulset.yaml` - Kafka StatefulSet
- `redis-deployment.yaml` - Redis deployment
- `osrm-deployment.yaml` - OSRM routing service
- Service manifests for each deployment
- ConfigMaps for environment-specific configuration
