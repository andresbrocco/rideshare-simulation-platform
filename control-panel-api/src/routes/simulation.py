import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from src.auth import verify_api_key
from src.models.simulation import (
    ControlResponse,
    SimulationStatusResponse,
    SpeedChangeRequest,
    SpeedChangeResponse,
)

router = APIRouter(dependencies=[Depends(verify_api_key)])

_simulation_start_wall_time: float | None = None


def get_engine(request: Request):
    return request.app.state.engine


@router.post("/start", response_model=ControlResponse)
def start_simulation(engine=Depends(get_engine)):
    """Start the simulation."""
    if engine.state.value == "running":
        raise HTTPException(status_code=400, detail="Simulation already running")

    global _simulation_start_wall_time
    _simulation_start_wall_time = time.time()

    engine.start()
    return ControlResponse(status="started")


@router.post("/pause", response_model=ControlResponse)
def pause_simulation(engine=Depends(get_engine)):
    """Initiate two-phase pause (draining then paused)."""
    if engine.state.value != "running":
        raise HTTPException(status_code=400, detail="Simulation not running")

    engine.pause()
    return ControlResponse(status="pausing", message="Draining in-flight trips")


@router.post("/resume", response_model=ControlResponse)
def resume_simulation(engine=Depends(get_engine)):
    """Resume from paused state."""
    if engine.state.value != "paused":
        raise HTTPException(status_code=400, detail="Simulation not paused")

    engine.resume()
    return ControlResponse(status="resumed")


@router.post("/stop", response_model=ControlResponse)
def stop_simulation(engine=Depends(get_engine)):
    """Stop the simulation."""
    if engine.state.value == "stopped":
        raise HTTPException(status_code=400, detail="Simulation already stopped")

    engine.stop()
    return ControlResponse(status="stopped")


@router.post("/reset", response_model=ControlResponse)
def reset_simulation(engine=Depends(get_engine)):
    """Reset simulation to initial state."""
    if hasattr(engine, "reset"):
        engine.reset()
    else:
        if engine.state.value != "stopped":
            engine.stop()

    global _simulation_start_wall_time
    _simulation_start_wall_time = None

    return ControlResponse(status="reset")


@router.put("/speed", response_model=SpeedChangeResponse)
def change_speed(request: SpeedChangeRequest, engine=Depends(get_engine)):
    """Change simulation speed multiplier (1, 10, or 100)."""
    if request.multiplier not in (1, 10, 100):
        raise HTTPException(
            status_code=400, detail="Invalid multiplier. Must be 1, 10, or 100"
        )

    engine.set_speed(request.multiplier)
    return SpeedChangeResponse(speed=request.multiplier)


@router.get("/status", response_model=SimulationStatusResponse)
def get_status(engine=Depends(get_engine)):
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
