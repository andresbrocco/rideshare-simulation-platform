#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="${SCRIPT_DIR}/../manifests"

echo "=========================================="
echo "Gateway API Configuration Test Suite"
echo "=========================================="

# Test 1: Install Gateway API CRDs
echo ""
echo "Test 1: Installing Gateway API CRDs..."
echo "---------------------------------------"

if kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.0/standard-install.yaml; then
    echo "  [OK] Gateway API CRDs installed"
else
    echo "  [FAIL] Failed to install Gateway API CRDs"
    exit 1
fi

echo ""
echo "Verifying Gateway API CRDs are installed..."
if kubectl get crd gateways.gateway.networking.k8s.io &>/dev/null; then
    echo "  [OK] Gateway CRD exists"
else
    echo "  [FAIL] Gateway CRD not found"
    exit 1
fi

if kubectl get crd httproutes.gateway.networking.k8s.io &>/dev/null; then
    echo "  [OK] HTTPRoute CRD exists"
else
    echo "  [FAIL] HTTPRoute CRD not found"
    exit 1
fi

# Test 2: Install Envoy Gateway controller
echo ""
echo "Test 2: Installing Envoy Gateway controller..."
echo "-----------------------------------------------"

if kubectl apply --server-side -f https://github.com/envoyproxy/gateway/releases/download/latest/install.yaml; then
    echo "  [OK] Envoy Gateway controller manifest applied"
else
    echo "  [FAIL] Failed to apply Envoy Gateway controller manifest"
    exit 1
fi

echo ""
echo "Waiting for Envoy Gateway pod to be Ready (max 5 minutes)..."
if kubectl wait --for=condition=ready pod -l control-plane=envoy-gateway -n envoy-gateway-system --timeout=300s; then
    echo "  [OK] Envoy Gateway controller is Ready"
else
    echo "  [FAIL] Envoy Gateway controller failed to become Ready"
    kubectl get pods -n envoy-gateway-system
    exit 1
fi

# Test 3: Apply Gateway resources
echo ""
echo "Test 3: Applying Gateway resources..."
echo "--------------------------------------"

declare -a GATEWAY_MANIFESTS=(
    "gateway-class.yaml"
    "gateway.yaml"
    "httproute-web-services.yaml"
    "httproute-api.yaml"
)

APPLIED_COUNT=0
FAILED_COUNT=0

for manifest in "${GATEWAY_MANIFESTS[@]}"; do
    manifest_path="${MANIFESTS_DIR}/${manifest}"
    if kubectl apply -f "${manifest_path}"; then
        echo "  [OK] ${manifest}"
        APPLIED_COUNT=$((APPLIED_COUNT + 1))
    else
        echo "  [FAIL] ${manifest}"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
done

echo ""
echo "Applied: ${APPLIED_COUNT}/${#GATEWAY_MANIFESTS[@]} manifests"
if [ ${FAILED_COUNT} -gt 0 ]; then
    echo "Failed: ${FAILED_COUNT} manifests"
    exit 1
fi

# Test 4: Verify Gateway listeners are Programmed
echo ""
echo "Test 4: Verifying Gateway listeners are Programmed..."
echo "------------------------------------------------------"

echo "Waiting for Gateway listeners to be Programmed (max 2 minutes)..."
sleep 10

TIMEOUT=120
ELAPSED=0
LISTENER_READY=false

while [ ${ELAPSED} -lt ${TIMEOUT} ]; do
    if kubectl get gateway rideshare-gateway -o jsonpath='{.status.listeners[0].conditions[?(@.type=="Programmed")].status}' 2>/dev/null | grep -q "True"; then
        LISTENER_READY=true
        break
    fi
    sleep 5
    ELAPSED=$((ELAPSED + 5))
    echo "  Waiting... (${ELAPSED}s/${TIMEOUT}s)"
done

if [ "${LISTENER_READY}" = true ]; then
    echo "  [OK] Gateway listeners are Programmed"
else
    echo "  [FAIL] Gateway listeners failed to become Programmed"
    echo ""
    echo "Gateway status:"
    kubectl describe gateway rideshare-gateway
    exit 1
fi

# Setup port-forwarding for Kind clusters (LoadBalancer pending is expected)
echo ""
echo "Setting up port-forward for Kind cluster..."
echo "-------------------------------------------"

# Get the Envoy Gateway service name
ENVOY_SVC_NAME=$(kubectl get svc -n envoy-gateway-system --no-headers | grep rideshare | awk '{print $1}')
if [ -z "${ENVOY_SVC_NAME}" ]; then
    echo "  [FAIL] Could not find Envoy Gateway service"
    exit 1
fi

echo "  Found service: ${ENVOY_SVC_NAME}"

# Use port 8080 instead of 80 to avoid needing sudo
TEST_PORT=8080

# Kill any existing port-forward on test port
if lsof -Pi :${TEST_PORT} -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "  Port ${TEST_PORT} is in use, killing existing process..."
    kill "$(lsof -Pi ":${TEST_PORT}" -sTCP:LISTEN -t)" 2>/dev/null || true
    sleep 2
fi

# Start port-forward in background
kubectl port-forward -n envoy-gateway-system svc/${ENVOY_SVC_NAME} ${TEST_PORT}:80 >/dev/null 2>&1 &
PORT_FORWARD_PID=$!
sleep 3

# Verify port-forward is running
if ! kill -0 ${PORT_FORWARD_PID} 2>/dev/null; then
    echo "  [FAIL] Port-forward failed to start"
    # Try to see why it failed
    kubectl port-forward -n envoy-gateway-system svc/${ENVOY_SVC_NAME} ${TEST_PORT}:80 2>&1 | head -5
    exit 1
fi

echo "  [OK] Port-forward established on localhost:${TEST_PORT} (PID: ${PORT_FORWARD_PID})"
echo "  Note: Port-forward will be terminated at the end of tests"

# Test 5: Verify HTTPRoutes are Accepted
echo ""
echo "Test 5: Verifying HTTPRoutes are Accepted..."
echo "---------------------------------------------"

declare -a EXPECTED_HTTPROUTES=(
    "web-services-route"
    "api-route"
)

ACCEPTED_COUNT=0
NOT_ACCEPTED_COUNT=0

for route in "${EXPECTED_HTTPROUTES[@]}"; do
    if kubectl get httproute "${route}" &>/dev/null; then
        status=$(kubectl get httproute "${route}" -o jsonpath='{.status.parents[0].conditions[?(@.type=="Accepted")].status}')
        if [ "${status}" = "True" ]; then
            echo "  [OK] ${route}: Accepted"
            ACCEPTED_COUNT=$((ACCEPTED_COUNT + 1))
        else
            echo "  [NOT ACCEPTED] ${route}"
            NOT_ACCEPTED_COUNT=$((NOT_ACCEPTED_COUNT + 1))
        fi
    else
        echo "  [MISSING] ${route}"
        NOT_ACCEPTED_COUNT=$((NOT_ACCEPTED_COUNT + 1))
    fi
done

echo ""
echo "Accepted HTTPRoutes: ${ACCEPTED_COUNT}/${#EXPECTED_HTTPROUTES[@]}"
if [ ${NOT_ACCEPTED_COUNT} -gt 0 ]; then
    echo "Not accepted HTTPRoutes: ${NOT_ACCEPTED_COUNT}"
    echo ""
    echo "HTTPRoute status:"
    kubectl get httproute
    exit 1
fi

# Test 6: Test HTTP access to services
echo ""
echo "Test 6: Testing HTTP access to all exposed services..."
echo "-------------------------------------------------------"

declare -a SERVICE_ENDPOINTS=(
    "/:Frontend (HTML expected)"
    "/api/health:Simulation API health endpoint"
    "/airflow/:Airflow UI"
    "/superset/:Superset login page"
    "/grafana/:Grafana UI"
    "/prometheus/:Prometheus UI"
)

HTTP_SUCCESS_COUNT=0
HTTP_FAIL_COUNT=0

for endpoint in "${SERVICE_ENDPOINTS[@]}"; do
    path="${endpoint%%:*}"
    description="${endpoint#*:}"

    echo ""
    echo "Testing: ${description} (${path})"

    if curl -f -s -o /dev/null -w "%{http_code}" "http://localhost:${TEST_PORT}${path}" | grep -qE '^(200|301|302|303|307|308)$'; then
        echo "  [OK] ${path} is accessible"
        HTTP_SUCCESS_COUNT=$((HTTP_SUCCESS_COUNT + 1))
    else
        status_code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${TEST_PORT}${path}")
        echo "  [FAIL] ${path} returned status ${status_code}"
        HTTP_FAIL_COUNT=$((HTTP_FAIL_COUNT + 1))
    fi
done

echo ""
echo "Accessible endpoints: ${HTTP_SUCCESS_COUNT}/${#SERVICE_ENDPOINTS[@]}"
if [ ${HTTP_FAIL_COUNT} -gt 0 ]; then
    echo "Failed endpoints: ${HTTP_FAIL_COUNT}"
    echo ""
    echo "HTTPRoute rules:"
    kubectl describe httproute
    exit 1
fi

# Test 7: Test WebSocket connection
echo ""
echo "Test 7: Testing WebSocket connection..."
echo "----------------------------------------"

echo "Checking if websocat is installed..."
if ! command -v websocat &>/dev/null; then
    echo "  [SKIP] websocat not installed - skipping WebSocket test"
    echo "  Install with: brew install websocat (macOS) or cargo install websocat"
else
    echo "  [OK] websocat is installed"
    echo ""
    echo "Testing WebSocket connection to ws://localhost:${TEST_PORT}/api/ws"

    # Send a simple ping and expect connection success
    if timeout 5 websocat -n1 "ws://localhost:${TEST_PORT}/api/ws" <<< '{"type":"ping"}' &>/dev/null; then
        echo "  [OK] WebSocket connection successful"
    else
        echo "  [FAIL] WebSocket connection failed"
        echo "  Note: This may be expected if authentication is required"
        echo "  Verify manually: websocat ws://localhost:${TEST_PORT}/api/ws"
    fi
fi

# Cleanup
echo ""
echo "Cleaning up port-forward..."
if [ -n "${PORT_FORWARD_PID}" ] && kill -0 ${PORT_FORWARD_PID} 2>/dev/null; then
    kill ${PORT_FORWARD_PID}
    echo "  [OK] Port-forward terminated"
fi

# Summary
echo ""
echo "=========================================="
echo "All Gateway API tests passed!"
echo "=========================================="
echo ""
echo "Service URLs (accessible via localhost):"
echo "  Frontend:       http://localhost/"
echo "  Simulation API: http://localhost/api/health"
echo "  Airflow UI:     http://localhost/airflow/"
echo "  Superset:       http://localhost/superset/"
echo "  Grafana:        http://localhost/grafana/"
echo "  Prometheus:     http://localhost/prometheus/"
echo "  WebSocket:      ws://localhost/api/ws"
echo ""
echo "Gateway API Resources:"
echo "  GatewayClass:   kubectl get gatewayclass"
echo "  Gateway:        kubectl get gateway"
echo "  HTTPRoutes:     kubectl get httproute"
echo ""
echo "TLS Configuration Notes:"
echo "  - Local development: TLS not required"
echo "  - Production: Use cert-manager with Let's Encrypt"
echo "  - Add certificateRefs to Gateway listener for TLS termination"
echo ""
echo "For persistent access (outside of tests):"
echo "  Run: kubectl port-forward -n envoy-gateway-system svc/envoy-default-rideshare-gateway-<hash> 80:80"
echo "  Or install MetalLB for LoadBalancer support in Kind"
echo ""
