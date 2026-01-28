"""Pub/sub channel definitions and message schemas for real-time visualization."""

from pydantic import BaseModel

# Channel names
CHANNEL_DRIVER_UPDATES = "driver-updates"
CHANNEL_RIDER_UPDATES = "rider-updates"
CHANNEL_TRIP_UPDATES = "trip-updates"
CHANNEL_SURGE_UPDATES = "surge_updates"

ALL_CHANNELS = [
    CHANNEL_DRIVER_UPDATES,
    CHANNEL_RIDER_UPDATES,
    CHANNEL_TRIP_UPDATES,
    CHANNEL_SURGE_UPDATES,
]


class DriverUpdateMessage(BaseModel):
    """Driver location and status update for visualization."""

    driver_id: str
    location: tuple[float, float]
    heading: float | None
    status: str
    trip_id: str | None
    timestamp: str


class RiderUpdateMessage(BaseModel):
    """Rider location update for visualization."""

    rider_id: str
    location: tuple[float, float]
    trip_id: str | None
    timestamp: str


class TripUpdateMessage(BaseModel):
    """Trip state update with full context."""

    trip_id: str
    state: str
    pickup: tuple[float, float]
    dropoff: tuple[float, float]
    driver_id: str | None
    rider_id: str
    fare: float
    surge_multiplier: float
    timestamp: str


class SurgeUpdateMessage(BaseModel):
    """Surge multiplier change for a zone."""

    zone_id: str
    previous_multiplier: float
    new_multiplier: float
    driver_count: int
    request_count: int
    timestamp: str
