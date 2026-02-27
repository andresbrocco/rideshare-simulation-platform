"""HTTP API for performance controller health and status."""

from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING, Literal

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    mode: str
    current_speed: float
    performance_index: float
    uptime_seconds: float


class StatusResponse(BaseModel):
    """Detailed controller state."""

    mode: str
    performance_index: float
    current_speed: float
    max_speed: float
    uptime_seconds: float


class ModeRequest(BaseModel):
    """Request body for setting controller mode."""

    mode: Literal["on", "off"]


# ------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------

app = FastAPI(title="Performance Controller API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FastAPIInstrumentor.instrument_app(app)


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Health check endpoint for Docker."""
    ctrl = _controller_ref
    if ctrl is None:
        return HealthResponse(
            status="starting",
            mode="off",
            current_speed=0.0,
            performance_index=0.0,
            uptime_seconds=time.monotonic() - _start_time,
        )

    return HealthResponse(
        status="healthy",
        mode=ctrl.mode,
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
            mode="off",
            performance_index=0.0,
            current_speed=0.0,
            max_speed=0.0,
            uptime_seconds=uptime,
        )

    return StatusResponse(
        mode=ctrl.mode,
        performance_index=ctrl.performance_index,
        current_speed=ctrl.current_speed,
        max_speed=ctrl._settings.controller.max_speed,
        uptime_seconds=uptime,
    )


@app.put("/controller/mode", response_model=StatusResponse)
def set_mode(body: ModeRequest) -> StatusResponse:
    """Set controller mode (on/off)."""
    ctrl = _controller_ref
    uptime = time.monotonic() - _start_time

    if ctrl is None:
        return StatusResponse(
            mode="off",
            performance_index=0.0,
            current_speed=0.0,
            max_speed=0.0,
            uptime_seconds=uptime,
        )

    ctrl.set_mode(body.mode)

    return StatusResponse(
        mode=ctrl.mode,
        performance_index=ctrl.performance_index,
        current_speed=ctrl.current_speed,
        max_speed=ctrl._settings.controller.max_speed,
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
