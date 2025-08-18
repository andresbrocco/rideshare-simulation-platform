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
    drivers_count: int
    riders_count: int
    active_trips_count: int
    uptime_seconds: float
