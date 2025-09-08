"""Health check models for service monitoring."""

from typing import Literal

from pydantic import BaseModel


class ServiceHealth(BaseModel):
    """Health status for a single service."""

    status: Literal["healthy", "degraded", "unhealthy"]
    latency_ms: float | None = None
    message: str | None = None


class StreamProcessorHealth(BaseModel):
    """Health status for stream processor service."""

    status: Literal["healthy", "degraded", "unhealthy"]
    latency_ms: float | None = None
    message: str | None = None
    kafka_connected: bool | None = None
    redis_connected: bool | None = None


class DetailedHealthResponse(BaseModel):
    """Detailed health check response for all services."""

    overall_status: Literal["healthy", "degraded", "unhealthy"]
    redis: ServiceHealth
    osrm: ServiceHealth
    kafka: ServiceHealth
    simulation_engine: ServiceHealth
    stream_processor: StreamProcessorHealth
    timestamp: str
