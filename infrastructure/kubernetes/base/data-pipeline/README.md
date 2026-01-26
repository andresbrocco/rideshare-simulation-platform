# Data Platform - Kubernetes Manifests

Base Kubernetes manifests for data platform services.

## Services Included

- **spark-master**: Spark master node
- **spark-worker**: Spark worker nodes (scalable)
- **minio**: S3-compatible object storage (lakehouse)
- **thrift-server**: Spark Thrift Server for dbt

## Usage

These base manifests are meant to be used with overlays (local or production).

```bash
# Apply with local overlay
kubectl apply -k ../../overlays/local

# Apply with production overlay
kubectl apply -k ../../overlays/production
```

## Manifest Files (to be added in Phase 6)

- `spark-master-deployment.yaml` - Spark master deployment
- `spark-worker-deployment.yaml` - Spark worker deployment (StatefulSet)
- `minio-statefulset.yaml` - MinIO StatefulSet with persistent volumes
- `thrift-server-deployment.yaml` - Thrift Server for SQL access
- Service manifests for each deployment
- PersistentVolumeClaims for storage
