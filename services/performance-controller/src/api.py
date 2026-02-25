"""HTTP API for performance controller health and status."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

import uvicorn
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

if TYPE_CHECKING:
    from .controller import PerformanceController

logger = logging.getLogger(__name__)

# Module-level controller reference, set by main.py after controller creation
_controller_ref: PerformanceController | None = None
_start_time: float = time.monotonic()


def set_controller(controller: PerformanceController) -> None:
    """Wire the controller instance for health/status endpoints."""
    global _controller_ref  # noqa: PLW0603
    _controller_ref = controller


# ------------------------------------------------------------------
# Response models
# ------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    baseline_complete: bool
    current_speed: int
    performance_index: float
    uptime_seconds: float


class BaselineResponse(BaseModel):
    """Baseline calibration parameters."""

    lag_capacity: float
    queue_capacity: float
    steady_throughput: float
    steady_rtr: float


class StatusResponse(BaseModel):
    """Detailed controller state."""

    performance_index: float
    current_speed: int
    target_speed: int
    consecutive_healthy: int
    baseline_complete: bool
    baseline: BaselineResponse | None
    uptime_seconds: float


# ------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------

app = FastAPI(title="Performance Controller API", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check endpoint for Docker."""
    ctrl = _controller_ref
    if ctrl is None:
        return HealthResponse(
            status="starting",
            baseline_complete=False,
            current_speed=0,
            performance_index=0.0,
            uptime_seconds=time.monotonic() - _start_time,
        )

    status = "healthy" if ctrl.baseline_complete else "calibrating"
    return HealthResponse(
        status=status,
        baseline_complete=ctrl.baseline_complete,
        current_speed=ctrl.current_speed,
        performance_index=ctrl.performance_index,
        uptime_seconds=time.monotonic() - _start_time,
    )


@app.get("/status", response_model=StatusResponse)
def get_status() -> StatusResponse:
    """Detailed controller state."""
    ctrl = _controller_ref
    uptime = time.monotonic() - _start_time

    if ctrl is None:
        return StatusResponse(
            performance_index=0.0,
            current_speed=0,
            target_speed=0,
            consecutive_healthy=0,
            baseline_complete=False,
            baseline=None,
            uptime_seconds=uptime,
        )

    baseline_resp = None
    if ctrl.baseline is not None:
        baseline_resp = BaselineResponse(
            lag_capacity=ctrl.baseline.lag_capacity,
            queue_capacity=ctrl.baseline.queue_capacity,
            steady_throughput=ctrl.baseline.steady_throughput,
            steady_rtr=ctrl.baseline.steady_rtr,
        )

    return StatusResponse(
        performance_index=ctrl.performance_index,
        current_speed=ctrl.current_speed,
        target_speed=ctrl._settings.controller.target_speed,
        consecutive_healthy=ctrl.consecutive_healthy,
        baseline_complete=ctrl.baseline_complete,
        baseline=baseline_resp,
        uptime_seconds=uptime,
    )


# ------------------------------------------------------------------
# Server helpers
# ------------------------------------------------------------------


def run_api_server(host: str, port: int) -> None:
    """Run the API server (blocking)."""
    uvicorn.run(app, host=host, port=port, log_level="warning")


def start_api_server_thread(host: str, port: int) -> threading.Thread:
    """Start API server in a background thread."""
    logger.info("Starting HTTP API server on %s:%d", host, port)
    thread = threading.Thread(
        target=run_api_server,
        args=(host, port),
        daemon=True,
        name="api-server",
    )
    thread.start()
    return thread
