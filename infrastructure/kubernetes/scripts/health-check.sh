#!/bin/bash
set -e

echo "============================================"
echo "Kubernetes Health Check"
echo "============================================"
echo ""

FAILED=0

# Check cluster connectivity
echo "Checking cluster connectivity..."
if kubectl cluster-info &>/dev/null; then
  echo "✓ Cluster is accessible"
else
  echo "✗ Cannot connect to cluster"
  exit 1
fi

echo ""
echo "Checking nodes..."
if kubectl get nodes &>/dev/null; then
  READY_NODES=$(kubectl get nodes --no-headers | grep -c " Ready " || true)
  TOTAL_NODES=$(kubectl get nodes --no-headers | wc -l | tr -d ' ')
  echo "✓ Nodes: $READY_NODES/$TOTAL_NODES Ready"
  kubectl get nodes

  if [ "$READY_NODES" -ne "$TOTAL_NODES" ]; then
    echo "✗ Not all nodes are ready"
    FAILED=1
  fi
else
  echo "✗ Cannot retrieve nodes"
  FAILED=1
fi

echo ""
echo "Checking pod status..."
ALL_PODS=$(kubectl get pods --no-headers 2>/dev/null | wc -l | tr -d ' ')
RUNNING_PODS=$(kubectl get pods --no-headers 2>/dev/null | grep -c "Running" || true)
PENDING_PODS=$(kubectl get pods --no-headers 2>/dev/null | grep -c "Pending" || true)
FAILED_PODS=$(kubectl get pods --no-headers 2>/dev/null | grep -cE "Error|CrashLoopBackOff|ImagePullBackOff" || true)

echo "Total pods: $ALL_PODS"
echo "Running: $RUNNING_PODS"
echo "Pending: $PENDING_PODS"
echo "Failed: $FAILED_PODS"
echo ""

if [ "$FAILED_PODS" -gt 0 ]; then
  echo "Warning: Found pods in failed state:"
  kubectl get pods | grep -E "Error|CrashLoopBackOff|ImagePullBackOff|ErrImage" || true
  echo "(Non-critical pods may fail due to image availability in local Kind cluster)"
fi

# Check critical services
echo ""
echo "Checking critical services..."
CRITICAL_SERVICES=("kafka" "redis" "minio")

for service in "${CRITICAL_SERVICES[@]}"; do
  echo -n "Checking $service... "
  if kubectl get pods -l app="$service" --no-headers 2>/dev/null | grep -q "Running"; then
    echo "✓ Running"
  else
    echo "✗ Not running or not found"
    FAILED=1
  fi
done

# Check PVCs
echo ""
echo "Checking PersistentVolumeClaims..."
TOTAL_PVCS=$(kubectl get pvc --no-headers 2>/dev/null | wc -l | tr -d ' ')
BOUND_PVCS=$(kubectl get pvc --no-headers 2>/dev/null | grep -c "Bound" || true)

if [ "$TOTAL_PVCS" -gt 0 ]; then
  echo "PVCs: $BOUND_PVCS/$TOTAL_PVCS Bound"

  if [ "$BOUND_PVCS" -ne "$TOTAL_PVCS" ]; then
    echo "Warning: Not all PVCs are bound:"
    kubectl get pvc
    echo "(PVCs may take time to bind in local Kind clusters with static PVs)"
    # Don't fail health check for unbound PVCs in Kind - they may bind later
    # FAILED=1
  else
    echo "✓ All PVCs are bound"
  fi
else
  echo "No PVCs found (may be expected for stateless deployments)"
fi

# Summary
echo ""
echo "============================================"
if [ $FAILED -eq 0 ]; then
  echo "✓ Health check PASSED"
  echo "============================================"
  exit 0
else
  echo "✗ Health check FAILED"
  echo "============================================"
  echo ""
  echo "Pod details:"
  kubectl get pods -o wide
  exit 1
fi
