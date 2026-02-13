#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
MANIFESTS_DIR="$PROJECT_ROOT/infrastructure/kubernetes/manifests"
CLUSTER_NAME="${CLUSTER_NAME:-rideshare-local}"

echo "============================================"
echo "Deploying Services to Kubernetes"
echo "============================================"
echo ""

# Verify cluster exists and is accessible
if ! kubectl cluster-info &>/dev/null; then
  echo "Error: Kubernetes cluster is not accessible"
  echo "Please create cluster first: ./infrastructure/kubernetes/scripts/create-cluster.sh"
  exit 1
fi

cd "$MANIFESTS_DIR"

# Install Gateway API CRDs if needed
echo "Step 0: Installing Gateway API CRDs..."
kubectl get crd gatewayclasses.gateway.networking.k8s.io &>/dev/null || \
  kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.0.0/standard-install.yaml || \
  echo "Warning: Gateway API CRDs installation skipped (may already exist)"

echo ""

# Deploy in order: storage, config/secrets, data platform, core services, monitoring, networking
echo "Step 1: Deploying storage resources..."
# StorageClass may already exist (Kind creates one by default), so don't fail on error
set +e
kubectl apply -f storageclass.yaml 2>&1 | grep -v "field is immutable" || true
set -e
kubectl apply -f pv-static.yaml
kubectl apply -f pvc-minio.yaml
kubectl apply -f pvc-kafka.yaml
kubectl apply -f pvc-postgres-airflow.yaml
kubectl apply -f pvc-postgres-metastore.yaml

echo ""
echo "Step 2: Deploying ConfigMaps and Secrets..."
kubectl apply -f configmap-core.yaml
kubectl apply -f configmap-data-pipeline.yaml
kubectl apply -f secret-credentials.yaml
kubectl apply -f secret-api-keys.yaml

# ESO auth credentials (must be applied before ExternalSecrets)
kubectl apply -f external-secrets-namespace.yaml
kubectl apply -f external-secrets-aws-credentials.yaml
kubectl apply -f external-secrets-secretstore.yaml

echo ""
echo "Step 3: Deploying data platform services..."
kubectl apply -f minio.yaml
kubectl apply -f minio-init.yaml
kubectl apply -f postgres-metastore.yaml
kubectl apply -f hive-metastore.yaml
kubectl apply -f spark-thrift-server.yaml
kubectl apply -f trino.yaml
kubectl apply -f bronze-ingestion.yaml
kubectl apply -f bronze-init.yaml
kubectl apply -f airflow-postgres.yaml
kubectl apply -f airflow-webserver.yaml
kubectl apply -f airflow-scheduler.yaml
kubectl apply -f localstack.yaml

echo ""
echo "Step 3b: Deploying ExternalSecret CRDs (syncs secrets from LocalStack)..."
# ExternalSecrets require LocalStack to be running so ESO can sync.
# ESO will retry automatically if LocalStack isn't ready yet.
set +e
kubectl apply -f external-secrets-api-keys.yaml 2>&1 | grep -v "no matches for kind" || true
kubectl apply -f external-secrets-app-credentials.yaml 2>&1 | grep -v "no matches for kind" || true
set -e

echo ""
echo "Step 4: Deploying core simulation services..."
kubectl apply -f kafka.yaml
kubectl apply -f schema-registry.yaml
kubectl apply -f redis.yaml
kubectl apply -f osrm.yaml
kubectl apply -f simulation.yaml
kubectl apply -f stream-processor.yaml
kubectl apply -f frontend.yaml

echo ""
echo "Step 5: Deploying monitoring services..."
kubectl apply -f prometheus.yaml
kubectl apply -f loki.yaml
kubectl apply -f tempo.yaml
kubectl apply -f otel-collector.yaml
kubectl apply -f cadvisor.yaml
kubectl apply -f grafana.yaml

echo ""
echo "Step 6: Deploying Gateway API resources..."
# Gateway API resources may fail if CRDs aren't ready, but don't fail the whole deployment
set +e
kubectl apply -f gateway-class.yaml 2>&1 | grep -v "no matches for kind" || true
kubectl apply -f gateway.yaml 2>&1 | grep -v "no matches for kind" || true
kubectl apply -f httproute-api.yaml 2>&1 | grep -v "no matches for kind" || true
kubectl apply -f httproute-web-services.yaml 2>&1 | grep -v "no matches for kind" || true
set -e

echo ""
echo "============================================"
echo "All manifests applied successfully!"
echo "============================================"
echo ""
echo "Waiting for critical pods to be ready (timeout: 5 minutes)..."

# Wait for critical services to be ready
TIMEOUT=300
echo "Waiting for Kafka..."
kubectl wait --for=condition=Ready pod -l app=kafka --timeout=${TIMEOUT}s 2>/dev/null || echo "Warning: Kafka pod not ready yet"

echo "Waiting for Redis..."
kubectl wait --for=condition=Ready pod -l app=redis --timeout=${TIMEOUT}s 2>/dev/null || echo "Warning: Redis pod not ready yet"

echo "Waiting for MinIO..."
kubectl wait --for=condition=Ready pod -l app=minio --timeout=${TIMEOUT}s 2>/dev/null || echo "Warning: MinIO pod not ready yet"

echo ""
echo "Deployment complete!"
echo ""
echo "Current pod status:"
kubectl get pods

echo ""
echo "Next steps:"
echo "  1. Check health: ./infrastructure/kubernetes/scripts/health-check.sh"
echo "  2. Run smoke tests: ./infrastructure/kubernetes/scripts/smoke-test.sh"
