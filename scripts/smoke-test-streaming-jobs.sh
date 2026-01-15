#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SPARK_CONTAINER="rideshare-spark-worker"
JOBS_PATH="/opt/spark-scripts/jobs"
PASSED=0
FAILED=0
TOTAL=8

STREAMING_JOBS=(
    "trips_streaming_job.py"
    "gps_pings_streaming_job.py"
    "driver_status_streaming_job.py"
    "surge_updates_streaming_job.py"
    "ratings_streaming_job.py"
    "payments_streaming_job.py"
    "driver_profiles_streaming_job.py"
    "rider_profiles_streaming_job.py"
)

echo "======================================"
echo "  Spark Streaming Jobs Smoke Test"
echo "======================================"
echo ""

if ! docker ps | grep -q "$SPARK_CONTAINER"; then
    echo -e "${RED}✗ Spark worker container not running${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Spark worker container running${NC}"
echo ""

for job_file in "${STREAMING_JOBS[@]}"; do
    job_name="${job_file%.py}"
    echo -n "Testing ${job_name}... "

    JOB_PATH="${JOBS_PATH}/${job_file}"

    if ! docker exec "$SPARK_CONTAINER" test -f "$JOB_PATH" 2>/dev/null; then
        echo -e "${RED}✗ FAILED${NC}"
        echo "  Error: Job file not found at ${JOB_PATH}"
        ((FAILED++))
        continue
    fi

    SYNTAX_CHECK=$(docker exec "$SPARK_CONTAINER" python3 -c "
import ast
with open('$JOB_PATH', 'r') as f:
    try:
        ast.parse(f.read())
    except SyntaxError as e:
        print(f'SyntaxError: {e}')
        exit(1)
" 2>&1 || true)

    if echo "$SYNTAX_CHECK" | grep -qi "SyntaxError\|IndentationError"; then
        echo -e "${RED}✗ FAILED${NC}"
        echo "  $SYNTAX_CHECK"
        ((FAILED++))
        continue
    fi

    IMPORT_CHECK=$(docker exec "$SPARK_CONTAINER" python3 -c "
import sys
sys.path.insert(0, '/opt/spark-scripts')
try:
    with open('$JOB_PATH', 'r') as f:
        code = f.read()
        if 'from streaming.framework' in code:
            print('Framework import found')
        else:
            print('Warning: No framework import found')
except Exception as e:
    print(f'Error: {e}')
    exit(1)
" 2>&1 || true)

    if echo "$IMPORT_CHECK" | grep -qi "^Error:"; then
        echo -e "${RED}✗ FAILED${NC}"
        echo "  $IMPORT_CHECK"
        ((FAILED++))
        continue
    fi

    echo -e "${GREEN}✓ PASSED${NC}"
    ((PASSED++))
done

echo ""
echo "======================================"
echo "  Test Results"
echo "======================================"
echo -e "Passed: ${GREEN}${PASSED}/${TOTAL}${NC}"
echo -e "Failed: ${RED}${FAILED}/${TOTAL}${NC}"
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo -e "${RED}Smoke tests failed. Fix errors before running integration tests.${NC}"
    exit 1
else
    echo -e "${GREEN}All smoke tests passed!${NC}"
    exit 0
fi
