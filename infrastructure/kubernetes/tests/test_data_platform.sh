#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="${SCRIPT_DIR}/../manifests"

echo "=========================================="
echo "Data Platform Manifests Test Suite"
echo "=========================================="

# Test 1: Apply all data platform manifests
echo ""
echo "Test 1: Applying data platform manifests..."
echo "------------------------------------------"

declare -a MANIFESTS=(
    "minio.yaml"
    "bronze-ingestion.yaml"
    "bronze-init.yaml"
    "spark-thrift-server.yaml"
    "localstack.yaml"
    "airflow-postgres.yaml"
    "airflow-webserver.yaml"
    "airflow-scheduler.yaml"
    "prometheus.yaml"
    "grafana.yaml"
)

APPLIED_COUNT=0
FAILED_COUNT=0

for manifest in "${MANIFESTS[@]}"; do
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
echo "Applied: ${APPLIED_COUNT}/${#MANIFESTS[@]} manifests"
if [ ${FAILED_COUNT} -gt 0 ]; then
    echo "Failed: ${FAILED_COUNT} manifests"
    exit 1
fi

# Test 2: Wait for pods to be Running
echo ""
echo "Test 2: Waiting for data platform pods to reach Running state (max 10 minutes)..."
echo "---------------------------------------------------------------------------------"

declare -a POD_LABELS=(
    "app=minio"
    "app=bronze-ingestion"
    "app=spark-thrift-server"
    "app=localstack"
    "app=airflow-postgres"
    "app=airflow-webserver"
    "app=airflow-scheduler"
    "app=prometheus"
    "app=grafana"
)

READY_COUNT=0
TIMEOUT_COUNT=0

for label in "${POD_LABELS[@]}"; do
    if kubectl wait --for=condition=Ready pod -l "${label}" --timeout=600s 2>/dev/null; then
        echo "  [OK] ${label}"
        READY_COUNT=$((READY_COUNT + 1))
    else
        echo "  [TIMEOUT] ${label}"
        TIMEOUT_COUNT=$((TIMEOUT_COUNT + 1))
    fi
done

echo ""
echo "Ready: ${READY_COUNT}/${#POD_LABELS[@]} pods"
if [ ${TIMEOUT_COUNT} -gt 0 ]; then
    echo "Timed out: ${TIMEOUT_COUNT} pods"
    echo ""
    echo "Pod status:"
    kubectl get pods -l 'app in (minio,bronze-ingestion,spark-thrift-server,localstack,airflow-postgres,airflow-webserver,airflow-scheduler,prometheus,grafana)'
    exit 1
fi

# Test 3: Verify total memory allocation
echo ""
echo "Test 3: Verifying resource allocations..."
echo "------------------------------------------"

# Expected memory allocations (adjusted to fit 5.6GB limit)
# Total: ~4.17GB (within 5.6GB spec)
# Format: app:memory
declare -a EXPECTED_MEMORY=(
    "minio:256Mi"
    "bronze-ingestion:512Mi"
    "spark-thrift-server:1024Mi"
    "localstack:512Mi"
    "airflow-postgres:256Mi"
    "airflow-webserver:384Mi"
    "airflow-scheduler:384Mi"
    "prometheus:256Mi"
    "grafana:192Mi"
)

# Verify memory limits are set correctly in manifests
CORRECT_COUNT=0
INCORRECT_COUNT=0

for entry in "${EXPECTED_MEMORY[@]}"; do
    app="${entry%%:*}"
    memory="${entry#*:}"
    manifest="${MANIFESTS_DIR}/${app}.yaml"

    if [ -f "${manifest}" ]; then
        if grep -q "memory: \"${memory}\"" "${manifest}"; then
            echo "  [OK] ${app}: ${memory}"
            CORRECT_COUNT=$((CORRECT_COUNT + 1))
        else
            echo "  [FAIL] ${app}: expected ${memory}"
            INCORRECT_COUNT=$((INCORRECT_COUNT + 1))
        fi
    else
        echo "  [SKIP] ${app}: manifest not found"
    fi
done

echo ""
echo "Correct allocations: ${CORRECT_COUNT}/${#EXPECTED_MEMORY[@]}"
if [ ${INCORRECT_COUNT} -gt 0 ]; then
    echo "Incorrect allocations: ${INCORRECT_COUNT}"
    exit 1
fi

# Test 4: Verify services are created
echo ""
echo "Test 4: Verifying services are created..."
echo "------------------------------------------"

declare -a EXPECTED_SERVICES=(
    "minio"
    "bronze-ingestion"
    "spark-thrift-server"
    "localstack"
    "airflow-postgres"
    "airflow-webserver"
    "prometheus"
    "grafana"
)

SERVICE_COUNT=0
MISSING_COUNT=0

for svc in "${EXPECTED_SERVICES[@]}"; do
    if kubectl get service "${svc}" &>/dev/null; then
        echo "  [OK] ${svc}"
        SERVICE_COUNT=$((SERVICE_COUNT + 1))
    else
        echo "  [MISSING] ${svc}"
        MISSING_COUNT=$((MISSING_COUNT + 1))
    fi
done

echo ""
echo "Services found: ${SERVICE_COUNT}/${#EXPECTED_SERVICES[@]}"
if [ ${MISSING_COUNT} -gt 0 ]; then
    echo "Missing services: ${MISSING_COUNT}"
    exit 1
fi

# Summary
echo ""
echo "=========================================="
echo "All data platform tests passed!"
echo "=========================================="
echo ""
echo "Next steps for manual verification:"
echo "  1. MinIO console: kubectl port-forward svc/minio 9001:9001"
echo "  2. Bronze ingestion health: kubectl port-forward svc/bronze-ingestion 8086:8080"
echo "  3. Spark thrift server: kubectl port-forward svc/spark-thrift-server 10000:10000"
echo "  4. Airflow UI: kubectl port-forward svc/airflow-webserver 8082:8082"
echo "  5. Prometheus UI: kubectl port-forward svc/prometheus 9090:9090"
echo "  6. Grafana UI: kubectl port-forward svc/grafana 3001:3001"
echo ""
