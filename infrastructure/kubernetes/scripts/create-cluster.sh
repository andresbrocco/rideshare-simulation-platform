#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CLUSTER_NAME="${CLUSTER_NAME:-rideshare-local}"
KIND_CONFIG="$PROJECT_ROOT/infrastructure/kubernetes/kind/cluster-config.yaml"

echo "============================================"
echo "Creating Kind Cluster: $CLUSTER_NAME"
echo "============================================"
echo ""

# Check if cluster already exists
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
  echo "Cluster '$CLUSTER_NAME' already exists."
  echo "To recreate, first run: kind delete cluster --name $CLUSTER_NAME"
  exit 0
fi

# Create cluster with Kind config
echo "Creating cluster with configuration: $KIND_CONFIG"
kind create cluster --config "$KIND_CONFIG" --name "$CLUSTER_NAME"

echo ""
echo "Waiting for cluster to be ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=120s

echo ""
echo "============================================"
echo "Cluster created successfully!"
echo "============================================"
echo ""
echo "Cluster info:"
kubectl cluster-info --context "kind-${CLUSTER_NAME}"

echo ""
echo "Nodes:"
kubectl get nodes

# Install External Secrets Operator via Helm chart.
# ESO syncs secrets from LocalStack (or real AWS) into K8s Secrets.
# The AWS_ENDPOINT_URL env var points the controller to LocalStack.
# For AWS migration: remove the --set env flags and use IAM roles instead.
echo ""
echo "============================================"
echo "Installing External Secrets Operator (v0.11.0)"
echo "============================================"
echo ""

if ! command -v helm &>/dev/null; then
  echo "Warning: Helm not found. Skipping ESO installation."
  echo "Install Helm (https://helm.sh/docs/intro/install/) and run manually:"
  echo "  helm repo add external-secrets https://charts.external-secrets.io"
  echo "  helm install external-secrets external-secrets/external-secrets \\"
  echo "    -n external-secrets --create-namespace \\"
  echo "    --set installCRDs=true --version 0.11.0 \\"
  echo "    --set 'env[0].name=AWS_ENDPOINT_URL' \\"
  echo "    --set 'env[0].value=http://localstack.default.svc.cluster.local:4566'"
else
  helm repo add external-secrets https://charts.external-secrets.io
  helm repo update external-secrets
  helm install external-secrets external-secrets/external-secrets \
    -n external-secrets --create-namespace \
    --set installCRDs=true \
    --version 0.11.0 \
    --set "env[0].name=AWS_ENDPOINT_URL" \
    --set "env[0].value=http://localstack.default.svc.cluster.local:4566"

  echo ""
  echo "Waiting for ESO pods to be ready..."
  kubectl wait --for=condition=Ready pods --all -n external-secrets --timeout=120s 2>/dev/null \
    || echo "Warning: ESO pods not ready yet. They may still be pulling images."
fi

echo ""
echo "Next steps:"
echo "  1. Deploy services: ./infrastructure/kubernetes/scripts/deploy-services.sh"
echo "  2. Check health: ./infrastructure/kubernetes/scripts/health-check.sh"
echo "  3. Run smoke tests: ./infrastructure/kubernetes/scripts/smoke-test.sh"
