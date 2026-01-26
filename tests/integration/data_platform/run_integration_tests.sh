#!/bin/bash
set -e

echo "=== Phase 1 Foundation Integration Tests ==="
echo ""

# Navigate to project root
cd "$(dirname "$0")/../.."

# Check if data platform services are running
echo "Checking service status..."
if ! docker compose ps | grep -q "rideshare-minio"; then
    echo "Starting data platform services..."
    docker compose --profile data-pipeline up -d
    echo "Waiting for services to be healthy (30s)..."
    sleep 30
fi

# Set AWS credentials for LocalStack
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"
export AWS_DEFAULT_REGION="us-east-1"

# Run integration tests
echo ""
echo "Running integration tests..."
./venv/bin/pytest data-pipeline/tests/test_foundation_integration.py -v

echo ""
echo "=== All integration tests passed! ==="
