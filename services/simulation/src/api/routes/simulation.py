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
from api.rate_limit import limiter

router = APIRouter(dependencies=[Depends(verify_api_key)])

_simulation_start_wall_time: float | None = None


def get_engine(request: Request) -> Any:
    return request.app.state.engine


def get_driver_registry(request: Request) -> Any:
    return getattr(request.app.state, "driver_registry", None)


EngineDep = Annotated[Any, Depends(get_engine)]
DriverRegistryDep = Annotated[Any, Depends(get_driver_registry)]


@router.post("/start", response_model=ControlResponse)
@limiter.limit("10/minute")
def start_simulation(request: Request, engine: EngineDep):
    """Start the simulation."""
    if engine.state.value == "running":
        raise HTTPException(status_code=400, detail="Simulation already running")

    global _simulation_start_wall_time
    _simulation_start_wall_time = time.time()

    engine.start()
    return ControlResponse(status="started")


@router.post("/pause", response_model=ControlResponse)
@limiter.limit("10/minute")
def pause_simulation(request: Request, engine: EngineDep):
    """Initiate two-phase pause (draining then paused)."""
    if engine.state.value != "running":
        raise HTTPException(status_code=400, detail="Simulation not running")

    engine.pause()
    return ControlResponse(status="pausing", message="Draining in-flight trips")


@router.post("/resume", response_model=ControlResponse)
@limiter.limit("10/minute")
def resume_simulation(request: Request, engine: EngineDep):
    """Resume from paused state."""
    if engine.state.value != "paused":
        raise HTTPException(status_code=400, detail="Simulation not paused")

    engine.resume()
    return ControlResponse(status="resumed")


@router.post("/stop", response_model=ControlResponse)
@limiter.limit("10/minute")
def stop_simulation(request: Request, engine: EngineDep):
    """Stop the simulation."""
    if engine.state.value == "stopped":
        raise HTTPException(status_code=400, detail="Simulation already stopped")

    engine.stop()
    return ControlResponse(status="stopped")


async def _broadcast_reset(connection_manager) -> None:
    """Broadcast reset message to all WebSocket clients."""
    await connection_manager.broadcast({"type": "simulation_reset", "data": {}})


@router.post("/reset", response_model=ControlResponse)
@limiter.limit("10/minute")
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
@limiter.limit("10/minute")
def change_speed(request: Request, body: SpeedChangeRequest, engine: EngineDep):
    """Change simulation speed multiplier (any positive integer)."""
    if body.multiplier < 1:
        raise HTTPException(
            status_code=400, detail="Invalid multiplier. Must be a positive integer"
        )

    engine.set_speed(body.multiplier)
    return SpeedChangeResponse(speed=body.multiplier)


@router.get("/status", response_model=SimulationStatusResponse)
@limiter.limit("30/minute")
def get_status(request: Request, engine: EngineDep, driver_registry: DriverRegistryDep):
    """Get current simulation status with detailed agent counts."""
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

    # Driver counts from registry (O(1) if get_all_status_counts exists)
    driver_counts = {"online": 0, "offline": 0, "en_route_pickup": 0, "en_route_destination": 0}
    if driver_registry and hasattr(driver_registry, "get_all_status_counts"):
        driver_counts = driver_registry.get_all_status_counts()
    elif hasattr(engine, "_active_drivers"):
        # Fallback: compute from engine's active drivers
        for driver in engine._active_drivers.values():
            status = getattr(driver, "status", "offline")
            if status in driver_counts:
                driver_counts[status] += 1

    # Rider counts (O(n), n = active riders)
    rider_counts = {"offline": 0, "waiting": 0, "in_trip": 0}
    if hasattr(engine, "_active_riders"):
        for rider in engine._active_riders.values():
            status = getattr(rider, "status", "offline")
            if status in rider_counts:
                rider_counts[status] += 1

    return SimulationStatusResponse(
        state=engine.state.value,
        speed_multiplier=engine.speed_multiplier,
        current_time=current_time_str,
        drivers_total=sum(driver_counts.values()),
        drivers_offline=driver_counts["offline"],
        drivers_online=driver_counts["online"],
        drivers_en_route_pickup=driver_counts["en_route_pickup"],
        drivers_en_route_destination=driver_counts["en_route_destination"],
        riders_total=sum(rider_counts.values()),
        riders_offline=rider_counts["offline"],
        riders_waiting=rider_counts["waiting"],
        riders_in_trip=rider_counts["in_trip"],
        active_trips_count=len(in_flight),
        uptime_seconds=uptime,
    )
