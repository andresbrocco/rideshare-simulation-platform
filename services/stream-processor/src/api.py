"""HTTP API for stream processor health and metrics."""

import logging
import threading

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from .metrics import get_metrics_collector

logger = logging.getLogger(__name__)


class LatencyStatsResponse(BaseModel):
    """Latency statistics."""

    avg_ms: float
    p95_ms: float
    count: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str  # "healthy", "degraded", "unhealthy"
    kafka_connected: bool
    redis_connected: bool
    uptime_seconds: float
    message: str | None = None


class MetricsResponse(BaseModel):
    """Metrics response."""

    # Throughput totals
    messages_consumed_total: int
    messages_published_total: int

    # Throughput rates
    messages_consumed_per_sec: float
    messages_published_per_sec: float

    # Aggregation
    gps_aggregation_ratio: float

    # Latency
    redis_publish_latency: LatencyStatsResponse

    # Errors
    publish_errors: int
    publish_errors_per_sec: float

    # Health
    kafka_connected: bool
    redis_connected: bool

    # Timing
    uptime_seconds: float
    timestamp: float


app = FastAPI(title="Stream Processor API", version="1.0.0")


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check endpoint for Docker and Simulation API."""
    collector = get_metrics_collector()
    snapshot = collector.get_snapshot()

    # Determine status
    if snapshot.kafka_connected and snapshot.redis_connected:
        status = "healthy"
        message = "All connections active"
    elif snapshot.kafka_connected or snapshot.redis_connected:
        status = "degraded"
        parts = []
        if not snapshot.kafka_connected:
            parts.append("Kafka disconnected")
        if not snapshot.redis_connected:
            parts.append("Redis disconnected")
        message = ", ".join(parts)
    else:
        status = "unhealthy"
        message = "All connections lost"

    return HealthResponse(
        status=status,
        kafka_connected=snapshot.kafka_connected,
        redis_connected=snapshot.redis_connected,
        uptime_seconds=snapshot.uptime_seconds,
        message=message,
    )


@app.get("/metrics", response_model=MetricsResponse)
def get_metrics() -> MetricsResponse:
    """Get performance metrics."""
    collector = get_metrics_collector()
    snapshot = collector.get_snapshot()

    return MetricsResponse(
        messages_consumed_total=snapshot.messages_consumed_total,
        messages_published_total=snapshot.messages_published_total,
        messages_consumed_per_sec=snapshot.messages_consumed_per_sec,
        messages_published_per_sec=snapshot.messages_published_per_sec,
        gps_aggregation_ratio=snapshot.gps_aggregation_ratio,
        redis_publish_latency=LatencyStatsResponse(
            avg_ms=snapshot.redis_publish_latency.avg_ms,
            p95_ms=snapshot.redis_publish_latency.p95_ms,
            count=snapshot.redis_publish_latency.count,
        ),
        publish_errors=snapshot.publish_errors,
        publish_errors_per_sec=snapshot.publish_errors_per_sec,
        kafka_connected=snapshot.kafka_connected,
        redis_connected=snapshot.redis_connected,
        uptime_seconds=snapshot.uptime_seconds,
        timestamp=snapshot.timestamp,
    )


def run_api_server(host: str, port: int) -> None:
    """Run the API server (blocking)."""
    uvicorn.run(app, host=host, port=port, log_level="warning")


def start_api_server_thread(host: str, port: int) -> threading.Thread:
    """Start API server in a background thread."""
    logger.info(f"Starting HTTP API server on {host}:{port}")
    thread = threading.Thread(
        target=run_api_server,
        args=(host, port),
        daemon=True,
        name="api-server",
    )
    thread.start()
    return thread
