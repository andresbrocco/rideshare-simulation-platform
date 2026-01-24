#!/bin/bash
# Setup script to create static PVs for testing
# Must be run before test_persistence.sh

set -e

echo "Setting up static PersistentVolumes for local testing..."

# Clean up any existing Failed PVs
kubectl delete pv local-pv-minio local-pv-airflow-postgres local-pv-superset-postgres local-pv-kafka 2>/dev/null || true

# Apply static PVs
kubectl apply -f infrastructure/kubernetes/manifests/pv-static.yaml

echo "Static PVs created successfully"
kubectl get pv
