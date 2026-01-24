#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "============================================"
echo "Kubernetes Smoke Tests"
echo "============================================"
echo ""

FAILED=0
TESTS_RUN=0
TESTS_PASSED=0

# Test 1: Kafka connectivity
echo "Test 1: Kafka connectivity"
echo "----------------------------------------------"
TESTS_RUN=$((TESTS_RUN + 1))

KAFKA_POD=$(kubectl get pods -l app=kafka --no-headers 2>/dev/null | awk '{print $1}' | head -n 1)
if [ -n "$KAFKA_POD" ]; then
  echo "Found Kafka pod: $KAFKA_POD"

  # Check if Kafka is responding
  if kubectl exec -i "$KAFKA_POD" -- kafka-broker-api-versions --bootstrap-server localhost:9092 &>/dev/null; then
    echo "✓ Kafka is responding to API requests"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "✗ Kafka is not responding"
    FAILED=1
  fi
else
  echo "✗ Kafka pod not found"
  FAILED=1
fi
echo ""

# Test 2: Redis connectivity
echo "Test 2: Redis connectivity"
echo "----------------------------------------------"
TESTS_RUN=$((TESTS_RUN + 1))

REDIS_POD=$(kubectl get pods -l app=redis --no-headers 2>/dev/null | awk '{print $1}' | head -n 1)
if [ -n "$REDIS_POD" ]; then
  echo "Found Redis pod: $REDIS_POD"

  # Check if Redis is responding
  if kubectl exec -i "$REDIS_POD" -- redis-cli ping 2>/dev/null | grep -q "PONG"; then
    echo "✓ Redis is responding to PING"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "✗ Redis is not responding"
    FAILED=1
  fi
else
  echo "✗ Redis pod not found"
  FAILED=1
fi
echo ""

# Test 3: MinIO connectivity
echo "Test 3: MinIO connectivity"
echo "----------------------------------------------"
TESTS_RUN=$((TESTS_RUN + 1))

MINIO_POD=$(kubectl get pods -l app=minio --no-headers 2>/dev/null | awk '{print $1}' | head -n 1)
if [ -n "$MINIO_POD" ]; then
  echo "Found MinIO pod: $MINIO_POD"

  # Check if MinIO is responding (health check endpoint)
  if kubectl exec -i "$MINIO_POD" -- curl -f http://localhost:9000/minio/health/live &>/dev/null; then
    echo "✓ MinIO health endpoint is responding"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "✗ MinIO health endpoint is not responding"
    FAILED=1
  fi
else
  echo "✗ MinIO pod not found"
  FAILED=1
fi
echo ""

# Test 4: Service DNS resolution
echo "Test 4: Service DNS resolution"
echo "----------------------------------------------"
TESTS_RUN=$((TESTS_RUN + 1))

# Use any running pod to test DNS
TEST_POD=$(kubectl get pods --field-selector=status.phase=Running --no-headers 2>/dev/null | awk '{print $1}' | head -n 1)
if [ -n "$TEST_POD" ]; then
  echo "Using pod $TEST_POD for DNS test"

  # Test DNS resolution for critical services
  DNS_TEST_FAILED=0
  for service in kafka redis minio; do
    if kubectl exec -i "$TEST_POD" -- nslookup "$service" &>/dev/null || \
       kubectl exec -i "$TEST_POD" -- getent hosts "$service" &>/dev/null || \
       kubectl exec -i "$TEST_POD" -- ping -c 1 "$service" &>/dev/null; then
      echo "  ✓ DNS resolution for $service"
    else
      echo "  ✗ DNS resolution failed for $service"
      DNS_TEST_FAILED=1
    fi
  done

  if [ $DNS_TEST_FAILED -eq 0 ]; then
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    FAILED=1
  fi
else
  echo "✗ No running pod found for DNS test"
  FAILED=1
fi
echo ""

# Test 5: Storage availability
echo "Test 5: Storage availability"
echo "----------------------------------------------"
TESTS_RUN=$((TESTS_RUN + 1))

BOUND_PVCS=$(kubectl get pvc --no-headers 2>/dev/null | grep -c "Bound" || true)
if [ "$BOUND_PVCS" -gt 0 ]; then
  echo "✓ Found $BOUND_PVCS bound PersistentVolumeClaims"

  # Verify MinIO can write to its volume
  if [ -n "$MINIO_POD" ]; then
    if kubectl exec -i "$MINIO_POD" -- touch /data/.smoke-test 2>/dev/null; then
      echo "✓ MinIO can write to persistent storage"
      kubectl exec -i "$MINIO_POD" -- rm /data/.smoke-test 2>/dev/null || true
      TESTS_PASSED=$((TESTS_PASSED + 1))
    else
      echo "✗ MinIO cannot write to persistent storage"
      FAILED=1
    fi
  else
    echo "Warning: MinIO pod not available for storage write test"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  fi
else
  echo "Warning: No bound PVCs found (may be expected for stateless deployments)"
  TESTS_PASSED=$((TESTS_PASSED + 1))
fi
echo ""

# Summary
echo "============================================"
echo "Smoke Test Results"
echo "============================================"
echo "Tests run: $TESTS_RUN"
echo "Tests passed: $TESTS_PASSED"
echo "Tests failed: $((TESTS_RUN - TESTS_PASSED))"
echo ""

if [ $FAILED -eq 0 ]; then
  echo "✓ All smoke tests PASSED!"
  exit 0
else
  echo "✗ Some smoke tests FAILED!"
  exit 1
fi
