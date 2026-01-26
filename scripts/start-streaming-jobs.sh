#!/bin/bash
# start-streaming-jobs.sh
# Submits all 8 Spark Structured Streaming jobs to the local Spark cluster.
# These jobs consume from Kafka and write to Bronze Delta tables in MinIO.
#
# Prerequisites:
#   - Docker Compose core and data-pipeline profiles running
#   - Kafka, Spark Master, Spark Worker, and MinIO healthy
#
# Usage:
#   ./scripts/start-streaming-jobs.sh           # Start all jobs
#   ./scripts/start-streaming-jobs.sh --status  # Check running jobs
#   ./scripts/start-streaming-jobs.sh --stop    # Stop all jobs

set -e

# Configuration
SPARK_WORKER_CONTAINER="rideshare-spark-worker"
SPARK_MASTER_URL="spark://spark-master:7077"
JOBS_PATH="/opt/spark_streaming/jobs"
KAFKA_BOOTSTRAP_SERVERS="kafka:29092"
SCHEMA_REGISTRY_URL="http://schema-registry:8085"

# All streaming jobs
JOBS=(
    "trips_streaming_job.py"
    "gps_pings_streaming_job.py"
    "driver_status_streaming_job.py"
    "surge_updates_streaming_job.py"
    "ratings_streaming_job.py"
    "payments_streaming_job.py"
    "driver_profiles_streaming_job.py"
    "rider_profiles_streaming_job.py"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if container is running
check_container() {
    local container=$1
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        return 0
    else
        return 1
    fi
}

# Wait for a service to be ready
wait_for_service() {
    local service=$1
    local max_attempts=$2
    local attempt=1

    log_info "Waiting for $service to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if check_container "$service"; then
            log_info "$service is ready"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    log_error "$service not ready after $max_attempts attempts"
    return 1
}

# Check Kafka connectivity from Spark worker
check_kafka() {
    log_info "Checking Kafka connectivity..."
    if docker exec "$SPARK_WORKER_CONTAINER" nc -z kafka 29092 2>/dev/null; then
        log_info "Kafka is reachable"
        return 0
    else
        log_error "Cannot reach Kafka from Spark worker"
        return 1
    fi
}

# Check MinIO connectivity
check_minio() {
    log_info "Checking MinIO connectivity..."
    if docker exec "$SPARK_WORKER_CONTAINER" nc -z minio 9000 2>/dev/null; then
        log_info "MinIO is reachable"
        return 0
    else
        log_error "Cannot reach MinIO from Spark worker"
        return 1
    fi
}

# Submit a single streaming job
submit_job() {
    local job_file=$1
    local job_name="${job_file%.py}"

    log_info "Submitting $job_name..."

    # Submit job in background within the container
    docker exec -d "$SPARK_WORKER_CONTAINER" \
        /opt/spark/bin/spark-submit \
        --master "$SPARK_MASTER_URL" \
        --deploy-mode client \
        --name "$job_name" \
        --conf "spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension" \
        --conf "spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog" \
        --conf "spark.hadoop.fs.s3a.endpoint=http://minio:9000" \
        --conf "spark.hadoop.fs.s3a.access.key=minioadmin" \
        --conf "spark.hadoop.fs.s3a.secret.key=minioadmin" \
        --conf "spark.hadoop.fs.s3a.path.style.access=true" \
        --conf "spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem" \
        --conf "spark.driver.extraJavaOptions=-DKAFKA_BOOTSTRAP_SERVERS=$KAFKA_BOOTSTRAP_SERVERS -DSCHEMA_REGISTRY_URL=$SCHEMA_REGISTRY_URL" \
        --conf "spark.executor.extraJavaOptions=-DKAFKA_BOOTSTRAP_SERVERS=$KAFKA_BOOTSTRAP_SERVERS -DSCHEMA_REGISTRY_URL=$SCHEMA_REGISTRY_URL" \
        "$JOBS_PATH/$job_file" \
        2>&1 | tee -a /tmp/streaming-job-$job_name.log &

    # Small delay between submissions to avoid overwhelming Spark
    sleep 2
}

# Check status of running jobs
check_status() {
    log_info "Checking streaming job status..."
    echo ""

    # Check Spark applications via REST API
    local apps=$(curl -s http://localhost:4040/api/v1/applications 2>/dev/null || echo "[]")

    if [ "$apps" = "[]" ] || [ -z "$apps" ]; then
        log_warn "No Spark applications found (Spark Master UI may not be accessible)"
        log_info "Checking processes in Spark worker container..."
        echo ""
        docker exec "$SPARK_WORKER_CONTAINER" ps aux | grep -E "spark-submit|streaming_job" | grep -v grep || log_warn "No streaming jobs running"
    else
        echo "$apps" | python3 -c "
import json, sys
apps = json.load(sys.stdin)
print(f'Found {len(apps)} Spark application(s):')
print('-' * 60)
for app in apps:
    print(f\"  Name: {app.get('name', 'N/A')}\")
    print(f\"  ID: {app.get('id', 'N/A')}\")
    print(f\"  Started: {app.get('startTime', 'N/A')}\")
    print('-' * 60)
" 2>/dev/null || echo "$apps"
    fi
}

# Stop all streaming jobs
stop_jobs() {
    log_info "Stopping all streaming jobs..."

    # Kill spark-submit processes in the container
    docker exec "$SPARK_WORKER_CONTAINER" pkill -f "spark-submit.*streaming_job" 2>/dev/null || true

    log_info "Stop signal sent to all streaming jobs"
    log_info "Jobs may take a few seconds to gracefully shutdown"
}

# Main function to start all jobs
start_all_jobs() {
    log_info "Starting Spark Structured Streaming Jobs"
    echo "=============================================="

    # Pre-flight checks
    log_info "Running pre-flight checks..."

    if ! check_container "$SPARK_WORKER_CONTAINER"; then
        log_error "Spark worker container not running"
        log_info "Start with: docker compose -f infrastructure/docker/compose.yml --profile data-pipeline up -d"
        exit 1
    fi

    if ! check_container "rideshare-kafka"; then
        log_error "Kafka container not running"
        log_info "Start with: docker compose -f infrastructure/docker/compose.yml --profile core up -d"
        exit 1
    fi

    check_kafka || exit 1
    check_minio || exit 1

    echo ""
    log_info "Pre-flight checks passed. Submitting jobs..."
    echo ""

    # Submit all jobs
    for job in "${JOBS[@]}"; do
        submit_job "$job"
    done

    echo ""
    log_info "All jobs submitted!"
    echo ""
    log_info "Monitor jobs at:"
    echo "  - Spark Master UI: http://localhost:4040"
    echo "  - Spark Worker UI: http://localhost:8081"
    echo ""
    log_info "Check status: ./scripts/start-streaming-jobs.sh --status"
    log_info "Stop jobs:    ./scripts/start-streaming-jobs.sh --stop"
    echo ""
    log_warn "Jobs run in background. First batch may take 30-60 seconds to process."
}

# Parse arguments
case "${1:-}" in
    --status)
        check_status
        ;;
    --stop)
        stop_jobs
        ;;
    --help|-h)
        echo "Usage: $0 [--status|--stop|--help]"
        echo ""
        echo "Options:"
        echo "  (none)    Start all streaming jobs"
        echo "  --status  Check status of running jobs"
        echo "  --stop    Stop all streaming jobs"
        echo "  --help    Show this help message"
        ;;
    *)
        start_all_jobs
        ;;
esac
