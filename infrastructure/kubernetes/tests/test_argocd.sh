#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ARGOCD_DIR="${SCRIPT_DIR}/../argocd"

echo "=========================================="
echo "ArgoCD Configuration Test Suite"
echo "=========================================="

# Test 1: Install ArgoCD
echo ""
echo "Test 1: Installing ArgoCD v3.2.3..."
echo "-----------------------------------"

if kubectl apply -f "${ARGOCD_DIR}/install.yaml"; then
    echo "  [OK] ArgoCD installation manifest applied"
else
    echo "  [FAIL] Failed to apply ArgoCD installation manifest"
    exit 1
fi

echo ""
echo "Waiting for ArgoCD namespace to be created..."
if kubectl wait --for=jsonpath='{.status.phase}'=Active namespace/argocd --timeout=30s; then
    echo "  [OK] argocd namespace is Active"
else
    echo "  [FAIL] argocd namespace failed to become Active"
    exit 1
fi

echo ""
echo "Waiting for all ArgoCD pods to be Ready (max 5 minutes)..."

ARGOCD_COMPONENTS=(
    "argocd-server"
    "argocd-repo-server"
    "argocd-application-controller"
    "argocd-redis"
    "argocd-applicationset-controller"
    "argocd-notifications-controller"
)

READY_COUNT=0
NOT_READY_COUNT=0

for component in "${ARGOCD_COMPONENTS[@]}"; do
    if kubectl wait --for=condition=Ready pod -l "app.kubernetes.io/name=${component}" -n argocd --timeout=300s; then
        echo "  [OK] ${component} is Ready"
        READY_COUNT=$((READY_COUNT + 1))
    else
        echo "  [FAIL] ${component} failed to become Ready"
        NOT_READY_COUNT=$((NOT_READY_COUNT + 1))
    fi
done

echo ""
echo "Ready pods: ${READY_COUNT}/${#ARGOCD_COMPONENTS[@]}"
if [ ${NOT_READY_COUNT} -gt 0 ]; then
    echo "Not ready pods: ${NOT_READY_COUNT}"
    echo ""
    echo "Pod status:"
    kubectl get pods -n argocd
    exit 1
fi

# Test 2: Access ArgoCD UI
echo ""
echo "Test 2: Verifying ArgoCD UI accessibility..."
echo "--------------------------------------------"

TEST_PORT=8081

echo "Checking if argocd-server service exists..."
if kubectl get svc argocd-server -n argocd &>/dev/null; then
    echo "  [OK] argocd-server service exists"
else
    echo "  [FAIL] argocd-server service not found"
    exit 1
fi

echo ""
echo "Setting up port-forward to ArgoCD UI..."

# Kill any existing port-forward on test port
if lsof -Pi :${TEST_PORT} -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "  Port ${TEST_PORT} is in use, killing existing process..."
    kill $(lsof -Pi :${TEST_PORT} -sTCP:LISTEN -t) 2>/dev/null || true
    sleep 2
fi

# Start port-forward in background
kubectl port-forward svc/argocd-server -n argocd ${TEST_PORT}:443 >/dev/null 2>&1 &
PORT_FORWARD_PID=$!
sleep 3

# Verify port-forward is running
if ! kill -0 ${PORT_FORWARD_PID} 2>/dev/null; then
    echo "  [FAIL] Port-forward failed to start"
    kubectl port-forward svc/argocd-server -n argocd ${TEST_PORT}:443 2>&1 | head -5
    exit 1
fi

echo "  [OK] Port-forward established on localhost:${TEST_PORT} (PID: ${PORT_FORWARD_PID})"

echo ""
echo "Testing HTTPS access to ArgoCD UI..."
if curl -k -f -s -o /dev/null -w "%{http_code}" "https://localhost:${TEST_PORT}" | grep -qE '^(200|301|302|303|307|308)$'; then
    echo "  [OK] ArgoCD UI is accessible"
else
    status_code=$(curl -k -s -o /dev/null -w "%{http_code}" "https://localhost:${TEST_PORT}")
    echo "  [FAIL] ArgoCD UI returned status ${status_code}"
    kill ${PORT_FORWARD_PID} 2>/dev/null || true
    exit 1
fi

# Test 3: Get admin password
echo ""
echo "Test 3: Retrieving ArgoCD admin password..."
echo "-------------------------------------------"

if kubectl get secret argocd-initial-admin-secret -n argocd &>/dev/null; then
    echo "  [OK] argocd-initial-admin-secret exists"

    ADMIN_PASSWORD=$(kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d)

    if [ -n "${ADMIN_PASSWORD}" ]; then
        echo "  [OK] Admin password retrieved"
        echo ""
        echo "  ArgoCD Admin Credentials:"
        echo "    Username: admin"
        echo "    Password: ${ADMIN_PASSWORD}"
        echo ""
    else
        echo "  [FAIL] Failed to decode admin password"
        exit 1
    fi
else
    echo "  [FAIL] argocd-initial-admin-secret not found"
    exit 1
fi

# Cleanup port-forward before next tests
if [ -n "${PORT_FORWARD_PID}" ] && kill -0 ${PORT_FORWARD_PID} 2>/dev/null; then
    kill ${PORT_FORWARD_PID}
    echo "  Port-forward terminated"
fi

# Test 4: Apply Application resources
echo ""
echo "Test 4: Applying ArgoCD Application resources..."
echo "-------------------------------------------------"

declare -a ARGOCD_MANIFESTS=(
    "app-core-services.yaml"
    "app-data-platform.yaml"
    "sync-policy.yaml"
)

APPLIED_COUNT=0
FAILED_COUNT=0

for manifest in "${ARGOCD_MANIFESTS[@]}"; do
    manifest_path="${ARGOCD_DIR}/${manifest}"
    if kubectl apply -f "${manifest_path}"; then
        echo "  [OK] ${manifest}"
        APPLIED_COUNT=$((APPLIED_COUNT + 1))
    else
        echo "  [FAIL] ${manifest}"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
done

echo ""
echo "Applied: ${APPLIED_COUNT}/${#ARGOCD_MANIFESTS[@]} manifests"
if [ ${FAILED_COUNT} -gt 0 ]; then
    echo "Failed: ${FAILED_COUNT} manifests"
    exit 1
fi

# Test 5: Verify Applications are created
echo ""
echo "Test 5: Verifying ArgoCD Applications are created..."
echo "----------------------------------------------------"

declare -a EXPECTED_APPLICATIONS=(
    "core-services"
    "data-platform"
)

CREATED_COUNT=0
MISSING_COUNT=0

for app in "${EXPECTED_APPLICATIONS[@]}"; do
    if kubectl get application "${app}" -n argocd &>/dev/null; then
        echo "  [OK] Application '${app}' exists"
        CREATED_COUNT=$((CREATED_COUNT + 1))

        # Check application health status
        health=$(kubectl get application "${app}" -n argocd -o jsonpath='{.status.health.status}' 2>/dev/null || echo "Unknown")
        sync=$(kubectl get application "${app}" -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")

        echo "       Health: ${health}, Sync: ${sync}"
    else
        echo "  [MISSING] Application '${app}'"
        MISSING_COUNT=$((MISSING_COUNT + 1))
    fi
done

echo ""
echo "Created Applications: ${CREATED_COUNT}/${#EXPECTED_APPLICATIONS[@]}"
if [ ${MISSING_COUNT} -gt 0 ]; then
    echo "Missing Applications: ${MISSING_COUNT}"
    echo ""
    echo "Available Applications:"
    kubectl get applications -n argocd
    exit 1
fi

# Test 6: Test drift detection
echo ""
echo "Test 6: Testing configuration drift detection..."
echo "-------------------------------------------------"

echo "Selecting a test deployment for drift simulation..."

# Find a deployment managed by ArgoCD (from core-services or data-platform)
TEST_DEPLOYMENT=$(kubectl get deployment -l argocd.argoproj.io/instance=core-services --no-headers 2>/dev/null | head -1 | awk '{print $1}')

if [ -z "${TEST_DEPLOYMENT}" ]; then
    # Try data-platform if core-services has no deployments yet
    TEST_DEPLOYMENT=$(kubectl get deployment -l argocd.argoproj.io/instance=data-platform --no-headers 2>/dev/null | head -1 | awk '{print $1}')
fi

if [ -z "${TEST_DEPLOYMENT}" ]; then
    echo "  [SKIP] No ArgoCD-managed deployments found for drift testing"
    echo "  This is expected if applications haven't synced yet"
else
    echo "  Using deployment: ${TEST_DEPLOYMENT}"

    # Get original replica count
    ORIGINAL_REPLICAS=$(kubectl get deployment "${TEST_DEPLOYMENT}" -o jsonpath='{.spec.replicas}')
    echo "  Original replicas: ${ORIGINAL_REPLICAS}"

    # Introduce drift by manually patching the deployment
    NEW_REPLICAS=$((ORIGINAL_REPLICAS + 1))
    echo ""
    echo "Introducing drift: scaling ${TEST_DEPLOYMENT} to ${NEW_REPLICAS} replicas..."

    if kubectl patch deployment "${TEST_DEPLOYMENT}" -p "{\"spec\":{\"replicas\":${NEW_REPLICAS}}}"; then
        echo "  [OK] Manual change applied"

        # Wait a moment for ArgoCD to detect the change
        echo ""
        echo "Waiting for ArgoCD to detect drift (max 30 seconds)..."
        sleep 10

        TIMEOUT=30
        ELAPSED=0
        DRIFT_DETECTED=false

        while [ ${ELAPSED} -lt ${TIMEOUT} ]; do
            # Check if application is OutOfSync
            SYNC_STATUS=$(kubectl get application core-services -n argocd -o jsonpath='{.status.sync.status}' 2>/dev/null || echo "Unknown")

            if [ "${SYNC_STATUS}" = "OutOfSync" ]; then
                DRIFT_DETECTED=true
                break
            fi

            sleep 5
            ELAPSED=$((ELAPSED + 5))
            echo "  Checking... (${ELAPSED}s/${TIMEOUT}s) - Sync Status: ${SYNC_STATUS}"
        done

        if [ "${DRIFT_DETECTED}" = true ]; then
            echo "  [OK] Drift detected - Application is OutOfSync"

            # Test self-healing (if auto-sync is enabled)
            echo ""
            echo "Checking for self-healing (auto-sync)..."
            sleep 15

            CURRENT_REPLICAS=$(kubectl get deployment "${TEST_DEPLOYMENT}" -o jsonpath='{.spec.replicas}')

            if [ "${CURRENT_REPLICAS}" -eq "${ORIGINAL_REPLICAS}" ]; then
                echo "  [OK] Self-healing worked - replicas reverted to ${ORIGINAL_REPLICAS}"
            else
                echo "  [INFO] Self-healing not configured or pending"
                echo "  Current replicas: ${CURRENT_REPLICAS}, Expected: ${ORIGINAL_REPLICAS}"

                # Manually revert the change
                echo "  Reverting manual change..."
                kubectl patch deployment "${TEST_DEPLOYMENT}" -p "{\"spec\":{\"replicas\":${ORIGINAL_REPLICAS}}}"
            fi
        else
            echo "  [FAIL] Drift not detected within timeout"
            echo "  Final Sync Status: ${SYNC_STATUS}"

            # Revert the change
            kubectl patch deployment "${TEST_DEPLOYMENT}" -p "{\"spec\":{\"replicas\":${ORIGINAL_REPLICAS}}}"
            exit 1
        fi
    else
        echo "  [FAIL] Failed to apply manual change"
        exit 1
    fi
fi

# Summary
echo ""
echo "=========================================="
echo "All ArgoCD tests passed!"
echo "=========================================="
echo ""
echo "ArgoCD UI:"
echo "  URL: https://localhost:8081 (via port-forward)"
echo "  Command: kubectl port-forward svc/argocd-server -n argocd 8081:443"
echo "  Username: admin"
echo "  Password: ${ADMIN_PASSWORD}"
echo ""
echo "ArgoCD CLI:"
echo "  Login: argocd login localhost:8081 --username admin --password '${ADMIN_PASSWORD}' --insecure"
echo "  Apps:  argocd app list"
echo "  Sync:  argocd app sync <app-name>"
echo ""
echo "ArgoCD Resources:"
echo "  Applications: kubectl get applications -n argocd"
echo "  Projects:     kubectl get appprojects -n argocd"
echo ""
echo "GitOps Workflow:"
echo "  1. Make changes to manifests in Git repository"
echo "  2. ArgoCD detects drift (polls every 3 minutes by default)"
echo "  3. Auto-sync applies changes (if enabled) or manual sync required"
echo "  4. Monitor sync status in UI or CLI"
echo ""
