# Backup and Restore Procedures

This document describes backup and restore procedures for stateful data in the Kubernetes cluster.

## Overview

The following PersistentVolumeClaims store critical application data:

| PVC Name | Service | Data Type | Storage Size |
|----------|---------|-----------|--------------|
| minio-data | MinIO | Delta Lake data (Bronze/Silver/Gold tables) | 10Gi |
| airflow-postgres-data | Airflow PostgreSQL | Workflow metadata, DAG runs, task history | 5Gi |
| postgres-metastore-data | Hive Metastore PostgreSQL | Table metadata, schema definitions | 5Gi |
| kafka-data | Kafka | Message logs, topic data | 5Gi |

## Storage Class Configuration

The cluster uses the `standard` StorageClass with the following properties:
- **Provisioner**: `rancher.io/local-path` (Kind's local-path-provisioner)
- **Reclaim Policy**: `Delete` (volumes are automatically deleted when PVC is deleted)
- **Volume Binding Mode**: `Immediate` (volume provisioned immediately when PVC is created)
- **Default**: Yes (automatically used if storageClassName not specified)

## Backup Procedures

### MinIO (Delta Lake Data)

MinIO stores Delta Lake tables and is the most critical data to back up.

```bash
# 1. Get the MinIO pod name
MINIO_POD=$(kubectl get pod -l app=minio -o jsonpath='{.items[0].metadata.name}')

# 2. Create a backup archive
kubectl exec $MINIO_POD -- tar czf /tmp/minio-backup.tar.gz -C /data .

# 3. Copy backup to local machine
kubectl cp $MINIO_POD:/tmp/minio-backup.tar.gz ./minio-backup-$(date +%Y%m%d-%H%M%S).tar.gz

# 4. Clean up temporary file
kubectl exec $MINIO_POD -- rm /tmp/minio-backup.tar.gz
```

### PostgreSQL Databases

#### Airflow PostgreSQL

```bash
# 1. Get the PostgreSQL pod name
POSTGRES_POD=$(kubectl get pod -l app=airflow-postgres -o jsonpath='{.items[0].metadata.name}')

# 2. Create SQL dump
kubectl exec $POSTGRES_POD -- pg_dump -U airflow -d airflow > airflow-backup-$(date +%Y%m%d-%H%M%S).sql

# Alternative: Binary dump (faster, smaller)
kubectl exec $POSTGRES_POD -- pg_dump -U airflow -d airflow -Fc > airflow-backup-$(date +%Y%m%d-%H%M%S).dump
```

#### Hive Metastore PostgreSQL

```bash
# 1. Get the PostgreSQL pod name
POSTGRES_POD=$(kubectl get pod -l app=postgres-metastore -o jsonpath='{.items[0].metadata.name}')

# 2. Create SQL dump
kubectl exec $POSTGRES_POD -- pg_dump -U hive -d metastore > metastore-backup-$(date +%Y%m%d-%H%M%S).sql

# Alternative: Binary dump (faster, smaller)
kubectl exec $POSTGRES_POD -- pg_dump -U hive -d metastore -Fc > metastore-backup-$(date +%Y%m%d-%H%M%S).dump
```

### Kafka

Kafka data is typically transient, but can be backed up if needed.

```bash
# 1. Get the Kafka pod name
KAFKA_POD=$(kubectl get pod -l app=kafka -o jsonpath='{.items[0].metadata.name}')

# 2. Create backup of Kafka logs
kubectl exec $KAFKA_POD -- tar czf /tmp/kafka-backup.tar.gz -C /var/lib/kafka/data .

# 3. Copy backup to local machine
kubectl cp $KAFKA_POD:/tmp/kafka-backup.tar.gz ./kafka-backup-$(date +%Y%m%d-%H%M%S).tar.gz

# 4. Clean up temporary file
kubectl exec $KAFKA_POD -- rm /tmp/kafka-backup.tar.gz
```

### PersistentVolume Snapshots (Alternative)

For production environments, consider using volume snapshots if your storage provider supports them:

```bash
# 1. Create VolumeSnapshot CRD (if not already installed)
kubectl apply -f https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/master/client/config/crd/snapshot.storage.k8s.io_volumesnapshots.yaml

# 2. Create a snapshot
cat <<EOF | kubectl apply -f -
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: minio-snapshot-$(date +%Y%m%d)
spec:
  volumeSnapshotClassName: standard
  source:
    persistentVolumeClaimName: minio-data
EOF

# 3. List snapshots
kubectl get volumesnapshot
```

**Note**: Volume snapshots are not supported by Kind's local-path-provisioner. Use file-based backups for local development.

## Restore Procedures

### MinIO (Delta Lake Data)

```bash
# 1. Ensure MinIO pod is running
kubectl get pod -l app=minio

# 2. Get the MinIO pod name
MINIO_POD=$(kubectl get pod -l app=minio -o jsonpath='{.items[0].metadata.name}')

# 3. Copy backup to pod
kubectl cp ./minio-backup-YYYYMMDD-HHMMSS.tar.gz $MINIO_POD:/tmp/minio-restore.tar.gz

# 4. Stop MinIO temporarily (optional, safer)
kubectl scale deployment minio --replicas=0
kubectl wait --for=delete pod -l app=minio --timeout=60s

# 5. Scale back up
kubectl scale deployment minio --replicas=1
kubectl wait --for=condition=Ready pod -l app=minio --timeout=120s

# 6. Get new pod name
MINIO_POD=$(kubectl get pod -l app=minio -o jsonpath='{.items[0].metadata.name}')

# 7. Clear existing data (CAUTION!)
kubectl exec $MINIO_POD -- sh -c 'rm -rf /data/*'

# 8. Extract backup
kubectl exec $MINIO_POD -- tar xzf /tmp/minio-restore.tar.gz -C /data

# 9. Clean up temporary file
kubectl exec $MINIO_POD -- rm /tmp/minio-restore.tar.gz

# 10. Verify data restored
kubectl exec $MINIO_POD -- ls -la /data
```

### PostgreSQL Databases

#### Airflow PostgreSQL

```bash
# 1. Get the PostgreSQL pod name
POSTGRES_POD=$(kubectl get pod -l app=airflow-postgres -o jsonpath='{.items[0].metadata.name}')

# 2. For SQL dump restore
kubectl exec -i $POSTGRES_POD -- psql -U airflow -d airflow < airflow-backup-YYYYMMDD-HHMMSS.sql

# 3. For binary dump restore
cat airflow-backup-YYYYMMDD-HHMMSS.dump | kubectl exec -i $POSTGRES_POD -- pg_restore -U airflow -d airflow --clean --if-exists

# 4. Verify restore
kubectl exec $POSTGRES_POD -- psql -U airflow -d airflow -c '\dt'
```

#### Hive Metastore PostgreSQL

```bash
# 1. Get the PostgreSQL pod name
POSTGRES_POD=$(kubectl get pod -l app=postgres-metastore -o jsonpath='{.items[0].metadata.name}')

# 2. For SQL dump restore
kubectl exec -i $POSTGRES_POD -- psql -U hive -d metastore < metastore-backup-YYYYMMDD-HHMMSS.sql

# 3. For binary dump restore
cat metastore-backup-YYYYMMDD-HHMMSS.dump | kubectl exec -i $POSTGRES_POD -- pg_restore -U hive -d metastore --clean --if-exists

# 4. Verify restore
kubectl exec $POSTGRES_POD -- psql -U hive -d metastore -c '\dt'
```

### Kafka

```bash
# 1. Scale down Kafka StatefulSet
kubectl scale statefulset kafka --replicas=0
kubectl wait --for=delete pod -l app=kafka --timeout=60s

# 2. Scale back up
kubectl scale statefulset kafka --replicas=1
kubectl wait --for=condition=Ready pod -l app=kafka --timeout=120s

# 3. Get the Kafka pod name
KAFKA_POD=$(kubectl get pod -l app=kafka -o jsonpath='{.items[0].metadata.name}')

# 4. Copy backup to pod
kubectl cp ./kafka-backup-YYYYMMDD-HHMMSS.tar.gz $KAFKA_POD:/tmp/kafka-restore.tar.gz

# 5. Clear existing data (CAUTION!)
kubectl exec $KAFKA_POD -- sh -c 'rm -rf /var/lib/kafka/data/*'

# 6. Extract backup
kubectl exec $KAFKA_POD -- tar xzf /tmp/kafka-restore.tar.gz -C /var/lib/kafka/data

# 7. Clean up temporary file
kubectl exec $KAFKA_POD -- rm /tmp/kafka-restore.tar.gz

# 8. Restart Kafka to reload data
kubectl delete pod -l app=kafka
kubectl wait --for=condition=Ready pod -l app=kafka --timeout=120s
```

## Disaster Recovery

### Complete Cluster Rebuild

If the entire cluster is lost:

1. **Recreate the Kind cluster**:
   ```bash
   kind create cluster --config infrastructure/kubernetes/kind/cluster-config.yaml --name rideshare-local
   ```

2. **Apply StorageClass and PVCs**:
   ```bash
   kubectl apply -f infrastructure/kubernetes/manifests/storageclass.yaml
   kubectl apply -f infrastructure/kubernetes/manifests/pvc-*.yaml
   ```

3. **Deploy all services**:
   ```bash
   kubectl apply -f infrastructure/kubernetes/manifests/
   ```

4. **Wait for all pods to be ready**:
   ```bash
   kubectl wait --for=condition=Ready pod --all --timeout=5m
   ```

5. **Restore data using procedures above**:
   - Restore MinIO data
   - Restore Airflow PostgreSQL
   - Restore Hive Metastore PostgreSQL
   - (Optional) Restore Kafka logs

### Individual PVC Recovery

**WARNING**: With the `Delete` reclaim policy, PVs are automatically deleted when PVCs are deleted. There is no recovery possible after PVC deletion.

To protect against accidental deletion:

```bash
# 1. Before deleting a PVC, always backup the data first (see backup procedures above)

# 2. For critical data, consider creating manual snapshots before maintenance:
MINIO_POD=$(kubectl get pod -l app=minio -o jsonpath='{.items[0].metadata.name}')
kubectl exec $MINIO_POD -- tar czf /tmp/emergency-backup.tar.gz -C /data .
kubectl cp $MINIO_POD:/tmp/emergency-backup.tar.gz ./emergency-backup-$(date +%Y%m%d-%H%M%S).tar.gz

# 3. If a PVC is accidentally deleted, you must:
#    a) Restore from backup (see restore procedures above)
#    b) Recreate the PVC: kubectl apply -f infrastructure/kubernetes/manifests/pvc-<service>.yaml
#    c) Deploy the service: kubectl apply -f infrastructure/kubernetes/manifests/<service>.yaml
#    d) Restore data from backup
```

## Backup Schedule Recommendations

For production environments, implement automated backup schedules:

| Data Type | Backup Frequency | Retention |
|-----------|------------------|-----------|
| MinIO (Delta Lake) | Daily at 2 AM | 30 days |
| Airflow PostgreSQL | Daily at 3 AM | 14 days |
| Hive Metastore PostgreSQL | Daily at 3 AM | 14 days |
| Kafka Logs | Not recommended (transient data) | N/A |

Use CronJobs in Kubernetes or external backup tools (Velero, Kasten K10) for automated backups.

## Testing Backup/Restore

Regularly test backup and restore procedures:

```bash
# 1. Create test data
# 2. Perform backup
# 3. Delete test data
# 4. Restore from backup
# 5. Verify data integrity
```

## Important Notes

- **Reclaim Policy**: The StorageClass uses `Delete` policy. When a PVC is deleted, the underlying PV is automatically deleted. **Always backup data before deleting PVCs**.
- **Local Development**: Kind's local-path-provisioner stores data on the Docker host at `/var/local-path-provisioner/`. Data persists only as long as the Kind cluster exists.
- **Data Loss Scenarios**:
  - Deleting a PVC will immediately delete its PV and all data (no recovery possible)
  - Deleting the Kind cluster (`kind delete cluster`) will permanently delete all PVs and data
  - Always maintain recent backups for critical data
- **Production**: For production, consider using:
  - StorageClass with `Retain` reclaim policy for critical data
  - Cloud provider storage classes (AWS EBS, GCE PD, Azure Disk) with automated snapshot capabilities
  - Automated backup solutions like Velero or cloud-native backup services
