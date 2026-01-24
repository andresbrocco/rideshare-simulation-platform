#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

echo "============================================"
echo "Testing Kubernetes Lifecycle Scripts"
echo "============================================"
echo ""

FAILED=0
TESTS_RUN=0
TESTS_PASSED=0

cd "$PROJECT_ROOT"

# Test 1: Create cluster
echo "Test 1: Creating Kind cluster"
echo "----------------------------------------------"
TESTS_RUN=$((TESTS_RUN + 1))
if ./infrastructure/kubernetes/scripts/create-cluster.sh; then
  echo "✓ Cluster creation script executed successfully"

  # Verify cluster exists
  if kind get clusters | grep -q "rideshare-local"; then
    echo "✓ Cluster 'rideshare-local' exists"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "✗ Cluster 'rideshare-local' not found"
    FAILED=1
  fi
else
  echo "✗ Cluster creation script failed"
  FAILED=1
fi
echo ""

# Test 2: Deploy services
echo "Test 2: Deploying services"
echo "----------------------------------------------"
TESTS_RUN=$((TESTS_RUN + 1))
if ./infrastructure/kubernetes/scripts/deploy-services.sh; then
  echo "✓ Service deployment script executed successfully"

  # Verify at least some core pods are running
  RUNNING_PODS=$(kubectl get pods --no-headers 2>/dev/null | grep -c "Running" || true)
  if [ "$RUNNING_PODS" -gt 0 ]; then
    echo "✓ Found $RUNNING_PODS pods in Running state"
    TESTS_PASSED=$((TESTS_PASSED + 1))
  else
    echo "✗ No pods found in Running state"
    FAILED=1
  fi
else
  echo "✗ Service deployment script failed"
  FAILED=1
fi
echo ""

# Test 3: Health check
echo "Test 3: Running health checks"
echo "----------------------------------------------"
TESTS_RUN=$((TESTS_RUN + 1))
if ./infrastructure/kubernetes/scripts/health-check.sh; then
  echo "✓ Health check script passed"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "✗ Health check script failed"
  FAILED=1
fi
echo ""

# Test 4: Smoke test
echo "Test 4: Running smoke tests"
echo "----------------------------------------------"
TESTS_RUN=$((TESTS_RUN + 1))
if ./infrastructure/kubernetes/scripts/smoke-test.sh; then
  echo "✓ Smoke test script passed"
  TESTS_PASSED=$((TESTS_PASSED + 1))
else
  echo "✗ Smoke test script failed"
  FAILED=1
fi
echo ""

# Test 5: Teardown with data preservation
echo "Test 5: Tearing down cluster with data preservation"
echo "----------------------------------------------"
TESTS_RUN=$((TESTS_RUN + 1))
if ./infrastructure/kubernetes/scripts/teardown.sh --preserve-data; then
  echo "✓ Teardown script executed successfully"

  # Verify backup created (use ls instead of find for macOS compatibility)
  BACKUP_FILE=$(ls -t /tmp/rideshare-k8s-backup-*.tar.gz 2>/dev/null | head -n 1)
  if [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
    # Check if file was created recently (within last 10 minutes)
    FILE_AGE=$(( $(date +%s) - $(stat -f %m "$BACKUP_FILE" 2>/dev/null || stat -c %Y "$BACKUP_FILE" 2>/dev/null) ))
    if [ "$FILE_AGE" -lt 600 ]; then
      echo "✓ Backup created: $BACKUP_FILE"
      TESTS_PASSED=$((TESTS_PASSED + 1))
    else
      echo "✗ Backup file is too old (${FILE_AGE}s old)"
      FAILED=1
    fi
  else
    echo "✗ Backup file not found in /tmp"
    FAILED=1
  fi

  # Verify cluster was deleted
  if ! kind get clusters | grep -q "rideshare-local"; then
    echo "✓ Cluster successfully deleted"
  else
    echo "✗ Cluster still exists after teardown"
    FAILED=1
  fi
else
  echo "✗ Teardown script failed"
  FAILED=1
fi
echo ""

# Summary
echo "============================================"
echo "Test Results Summary"
echo "============================================"
echo "Tests run: $TESTS_RUN"
echo "Tests passed: $TESTS_PASSED"
echo "Tests failed: $((TESTS_RUN - TESTS_PASSED))"
echo ""

if [ $FAILED -eq 0 ]; then
  echo "✓ All lifecycle tests passed!"
  exit 0
else
  echo "✗ Some lifecycle tests failed!"
  exit 1
fi
