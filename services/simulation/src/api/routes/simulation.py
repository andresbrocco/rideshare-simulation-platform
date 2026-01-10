import time
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from api.auth import verify_api_key
from api.models.simulation import (
    ControlResponse,
    SimulationStatusResponse,
    SpeedChangeRequest,
    SpeedChangeResponse,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])

_simulation_start_wall_time: float | None = None


def get_engine(request: Request) -> Any:
    return request.app.state.engine


EngineDep = Annotated[Any, Depends(get_engine)]


@router.post("/start", response_model=ControlResponse)
def start_simulation(engine: EngineDep):
    """Start the simulation."""
    if engine.state.value == "running":
        raise HTTPException(status_code=400, detail="Simulation already running")

    global _simulation_start_wall_time
    _simulation_start_wall_time = time.time()

    engine.start()
    return ControlResponse(status="started")


@router.post("/pause", response_model=ControlResponse)
def pause_simulation(engine: EngineDep):
    """Initiate two-phase pause (draining then paused)."""
    if engine.state.value != "running":
        raise HTTPException(status_code=400, detail="Simulation not running")

    engine.pause()
    return ControlResponse(status="pausing", message="Draining in-flight trips")


@router.post("/resume", response_model=ControlResponse)
def resume_simulation(engine: EngineDep):
    """Resume from paused state."""
    if engine.state.value != "paused":
        raise HTTPException(status_code=400, detail="Simulation not paused")

    engine.resume()
    return ControlResponse(status="resumed")


@router.post("/stop", response_model=ControlResponse)
def stop_simulation(engine: EngineDep):
    """Stop the simulation."""
    if engine.state.value == "stopped":
        raise HTTPException(status_code=400, detail="Simulation already stopped")

    engine.stop()
    return ControlResponse(status="stopped")


async def _broadcast_reset(connection_manager) -> None:
    """Broadcast reset message to all WebSocket clients."""
    await connection_manager.broadcast({"type": "simulation_reset", "data": {}})


@router.post("/reset", response_model=ControlResponse)
def reset_simulation(request: Request, engine: EngineDep, background_tasks: BackgroundTasks):
    """Reset simulation to initial state, clearing all data."""
    # Call engine reset (handles most clearing including database)
    engine.reset()

    # Clear components not accessible from engine
    driver_registry = getattr(request.app.state, "driver_registry", None)
    surge_calculator = getattr(request.app.state, "surge_calculator", None)

    if driver_registry and hasattr(driver_registry, "clear"):
        driver_registry.clear()
    if surge_calculator and hasattr(surge_calculator, "clear"):
        surge_calculator.clear()

    # Reset API-level state
    global _simulation_start_wall_time
    _simulation_start_wall_time = None

    # Broadcast reset message to WebSocket clients
    connection_manager = getattr(request.app.state, "connection_manager", None)
    if connection_manager:
        background_tasks.add_task(_broadcast_reset, connection_manager)

    return ControlResponse(status="reset", message="Simulation reset to initial state")


@router.put("/speed", response_model=SpeedChangeResponse)
def change_speed(request: SpeedChangeRequest, engine: EngineDep):
    """Change simulation speed multiplier (any positive integer)."""
    if request.multiplier < 1:
        raise HTTPException(
            status_code=400, detail="Invalid multiplier. Must be a positive integer"
        )

    engine.set_speed(request.multiplier)
    return SpeedChangeResponse(speed=request.multiplier)


@router.get("/status", response_model=SimulationStatusResponse)
def get_status(engine: EngineDep):
    """Get current simulation status."""
    current_time = engine.current_time()
    if isinstance(current_time, datetime):
        current_time_str = current_time.astimezone(UTC).isoformat()
    else:
        current_time_str = datetime.now(UTC).isoformat()

    in_flight = []
    if hasattr(engine, "_get_in_flight_trips"):
        in_flight = engine._get_in_flight_trips()

    uptime = 0.0
    if _simulation_start_wall_time is not None:
        uptime = time.time() - _simulation_start_wall_time

    return SimulationStatusResponse(
        state=engine.state.value,
        speed_multiplier=engine.speed_multiplier,
        current_time=current_time_str,
        drivers_count=engine.active_driver_count,
        riders_count=engine.active_rider_count,
        active_trips_count=len(in_flight),
        uptime_seconds=uptime,
    )
