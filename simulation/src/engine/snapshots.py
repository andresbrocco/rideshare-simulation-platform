"""Immutable snapshot dataclasses for thread-safe state transfer.

These frozen dataclasses provide a way to safely transfer simulation state
between the SimPy thread and FastAPI thread without risk of mutation.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AgentSnapshot:
    """Immutable snapshot of an agent's state."""

    id: str
    type: str  # "driver" or "rider"
    status: str
    location: tuple[float, float]
    active_trip_id: str | None
    zone_id: str | None

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "location": self.location,
            "active_trip_id": self.active_trip_id,
            "zone_id": self.zone_id,
        }


@dataclass(frozen=True)
class TripSnapshot:
    """Immutable snapshot of a trip's state."""

    trip_id: str
    state: str
    driver_id: str | None
    rider_id: str
    pickup_location: tuple[float, float]
    dropoff_location: tuple[float, float]
    created_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot to dictionary with datetime as ISO string."""
        return {
            "trip_id": self.trip_id,
            "state": self.state,
            "driver_id": self.driver_id,
            "rider_id": self.rider_id,
            "pickup_location": self.pickup_location,
            "dropoff_location": self.dropoff_location,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class SimulationSnapshot:
    """Immutable snapshot of the entire simulation state."""

    timestamp: datetime
    simulation_time: float
    is_running: bool
    is_paused: bool
    speed_multiplier: float
    driver_count: int
    rider_count: int
    active_trip_count: int
    drivers: tuple[AgentSnapshot, ...]
    riders: tuple[AgentSnapshot, ...]
    active_trips: tuple[TripSnapshot, ...]
    status_counts: dict[str, int]
    zone_counts: dict[str, dict[str, int]]

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot to dictionary with nested snapshots serialized."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "simulation_time": self.simulation_time,
            "is_running": self.is_running,
            "is_paused": self.is_paused,
            "speed_multiplier": self.speed_multiplier,
            "driver_count": self.driver_count,
            "rider_count": self.rider_count,
            "active_trip_count": self.active_trip_count,
            "drivers": [d.to_dict() for d in self.drivers],
            "riders": [r.to_dict() for r in self.riders],
            "active_trips": [t.to_dict() for t in self.active_trips],
            "status_counts": self.status_counts,
            "zone_counts": self.zone_counts,
        }
