#!/bin/bash
set -e

echo "Testing PersistentVolumeClaims and Data Persistence..."

# Test 1: Apply StorageClass
echo "Test 1: Applying StorageClass"
kubectl apply -f infrastructure/kubernetes/manifests/storageclass.yaml

# Verify StorageClass is created
echo "Verifying StorageClass exists"
kubectl get storageclass standard -o yaml

# Test 2: Apply PersistentVolumeClaims
echo "Test 2: Applying PersistentVolumeClaims"
kubectl apply -f infrastructure/kubernetes/manifests/pvc-minio.yaml
kubectl apply -f infrastructure/kubernetes/manifests/pvc-postgres-airflow.yaml
kubectl apply -f infrastructure/kubernetes/manifests/pvc-postgres-superset.yaml
kubectl apply -f infrastructure/kubernetes/manifests/pvc-kafka.yaml

# Test 3: Verify PVCs are Bound (max 2 minutes)
echo "Test 3: Verifying PVCs reach Bound state"
kubectl wait --for=jsonpath='{.status.phase}'=Bound pvc/minio-data --timeout=120s
kubectl wait --for=jsonpath='{.status.phase}'=Bound pvc/airflow-postgres-data --timeout=120s
kubectl wait --for=jsonpath='{.status.phase}'=Bound pvc/superset-postgres-data --timeout=120s
kubectl wait --for=jsonpath='{.status.phase}'=Bound pvc/kafka-data --timeout=120s

# Verify all PVCs show STATUS Bound
echo "Verifying all PVCs show Bound status"
kubectl get pvc minio-data -o jsonpath='{.status.phase}' | grep -q "Bound"
kubectl get pvc airflow-postgres-data -o jsonpath='{.status.phase}' | grep -q "Bound"
kubectl get pvc superset-postgres-data -o jsonpath='{.status.phase}' | grep -q "Bound"
kubectl get pvc kafka-data -o jsonpath='{.status.phase}' | grep -q "Bound"

# Test 4: Verify PersistentVolumes are automatically provisioned
echo "Test 4: Verifying PersistentVolumes are automatically provisioned"
MINIO_PV=$(kubectl get pvc minio-data -o jsonpath='{.spec.volumeName}')
AIRFLOW_PV=$(kubectl get pvc airflow-postgres-data -o jsonpath='{.spec.volumeName}')
SUPERSET_PV=$(kubectl get pvc superset-postgres-data -o jsonpath='{.spec.volumeName}')
KAFKA_PV=$(kubectl get pvc kafka-data -o jsonpath='{.spec.volumeName}')

echo "Verifying PersistentVolumes exist"
kubectl get pv "$MINIO_PV" -o yaml
kubectl get pv "$AIRFLOW_PV" -o yaml
kubectl get pv "$SUPERSET_PV" -o yaml
kubectl get pv "$KAFKA_PV" -o yaml

# Verify PVs are bound to their respective PVCs
kubectl get pv "$MINIO_PV" -o jsonpath='{.status.phase}' | grep -q "Bound"
kubectl get pv "$AIRFLOW_PV" -o jsonpath='{.status.phase}' | grep -q "Bound"
kubectl get pv "$SUPERSET_PV" -o jsonpath='{.status.phase}' | grep -q "Bound"
kubectl get pv "$KAFKA_PV" -o jsonpath='{.status.phase}' | grep -q "Bound"

# Test 5: Test data persistence across pod restarts
echo "Test 5: Testing data persistence with MinIO write/delete/verify cycle"

# Deploy MinIO with PVC
echo "Deploying MinIO with PVC"
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio-test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minio-test
  template:
    metadata:
      labels:
        app: minio-test
    spec:
      containers:
      - name: minio
        image: quay.io/minio/minio:latest
        command: ["minio", "server", "/data"]
        ports:
        - containerPort: 9000
        env:
        - name: MINIO_ROOT_USER
          value: minioadmin
        - name: MINIO_ROOT_PASSWORD
          value: minioadmin
        volumeMounts:
        - name: data
          mountPath: /data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: minio-data
---
apiVersion: v1
kind: Service
metadata:
  name: minio-test
spec:
  type: ClusterIP
  ports:
  - port: 9000
    targetPort: 9000
  selector:
    app: minio-test
EOF

# Wait for MinIO pod to be ready
echo "Waiting for MinIO test pod to be ready"
kubectl wait --for=condition=Ready pod -l app=minio-test --timeout=60s

# Write a test file to MinIO data directory
echo "Writing test file to MinIO volume"
MINIO_POD=$(kubectl get pod -l app=minio-test -o jsonpath='{.items[0].metadata.name}')
kubectl exec "$MINIO_POD" -- sh -c 'echo "persistence-test-data" > /data/.testfile'

# Verify file exists
echo "Verifying test file exists before pod restart"
kubectl exec "$MINIO_POD" -- cat /data/.testfile | grep -q "persistence-test-data"

# Delete the pod
echo "Deleting MinIO test pod"
kubectl delete pod "$MINIO_POD"

# Wait for new pod to be ready
echo "Waiting for new MinIO test pod to be ready"
kubectl wait --for=condition=Ready pod -l app=minio-test --timeout=60s

# Verify file still exists after pod restart
echo "Verifying test file persists after pod restart"
NEW_MINIO_POD=$(kubectl get pod -l app=minio-test -o jsonpath='{.items[0].metadata.name}')
kubectl exec "$NEW_MINIO_POD" -- cat /data/.testfile | grep -q "persistence-test-data"

# Cleanup test deployment
echo "Cleaning up test deployment"
kubectl delete deployment minio-test
kubectl delete service minio-test

echo "All persistence tests passed!"
