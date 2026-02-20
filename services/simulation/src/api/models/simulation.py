from typing import Literal

from pydantic import BaseModel


class SpeedChangeRequest(BaseModel):
    multiplier: int


class SpeedChangeResponse(BaseModel):
    speed: int


class ControlResponse(BaseModel):
    status: str
    message: str | None = None


class SimulationStatusResponse(BaseModel):
    state: Literal["stopped", "running", "draining", "paused"]
    speed_multiplier: int
    current_time: str
    # Detailed driver metrics
    drivers_total: int
    drivers_offline: int
    drivers_available: int
    drivers_en_route_pickup: int
    drivers_on_trip: int
    # Detailed rider metrics
    riders_total: int
    riders_idle: int
    riders_requesting: int
    riders_on_trip: int
    # Trips
    active_trips_count: int
    uptime_seconds: float
