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
echo "✓ Cluster created successfully!"
echo "============================================"
echo ""
echo "Cluster info:"
kubectl cluster-info --context "kind-${CLUSTER_NAME}"

echo ""
echo "Nodes:"
kubectl get nodes

echo ""
echo "Next steps:"
echo "  1. Deploy services: ./infrastructure/kubernetes/scripts/deploy-services.sh"
echo "  2. Check health: ./infrastructure/kubernetes/scripts/health-check.sh"
echo "  3. Run smoke tests: ./infrastructure/kubernetes/scripts/smoke-test.sh"
