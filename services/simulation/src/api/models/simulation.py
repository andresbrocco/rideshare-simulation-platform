from typing import Literal

from pydantic import BaseModel, Field


class SpeedChangeRequest(BaseModel):
    multiplier: float = Field(ge=0.5, le=128.0)


class SpeedChangeResponse(BaseModel):
    speed: float


class ControlResponse(BaseModel):
    status: str
    message: str | None = None


class SimulationStatusResponse(BaseModel):
    state: Literal["stopped", "running", "draining", "paused"]
    speed_multiplier: float
    current_time: str
    # Detailed driver metrics
    drivers_total: int
    drivers_offline: int
    drivers_available: int
    drivers_en_route_pickup: int
    drivers_on_trip: int
    drivers_driving_closer_to_home: int
    # Detailed rider metrics
    riders_total: int
    riders_idle: int
    riders_requesting: int
    riders_awaiting_pickup: int
    riders_on_trip: int
    # Trips
    active_trips_count: int
    uptime_seconds: float
    real_time_ratio: float | None = None
