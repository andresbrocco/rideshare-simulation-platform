"""Agent DNA models defining behavioral and profile attributes."""

from enum import Enum
from math import asin, cos, radians, sin, sqrt
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ShiftPreference(str, Enum):
    """Driver shift preference."""

    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    FLEXIBLE = "flexible"


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two coordinates using Haversine formula."""
    earth_radius_km = 6371.0

    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)

    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * asin(sqrt(a))

    return earth_radius_km * c


def validate_sao_paulo_coordinates(coords: tuple[float, float]) -> tuple[float, float]:
    """Validate coordinates are within Sao Paulo bounds."""
    # Bounds matching actual districts from zones.geojson
    lat, lon = coords
    if not (-23.75 <= lat <= -23.40):
        raise ValueError(f"Latitude {lat} outside Sao Paulo bounds (-23.75 to -23.40)")
    if not (-46.85 <= lon <= -46.35):
        raise ValueError(f"Longitude {lon} outside Sao Paulo bounds (-46.85 to -46.35)")
    return coords


class DriverDNA(BaseModel):
    """Driver behavioral and profile DNA."""

    # Behavioral parameters (immutable)
    acceptance_rate: float = Field(ge=0.0, le=1.0)
    cancellation_tendency: float = Field(ge=0.0, le=1.0)
    service_quality: float = Field(ge=0.0, le=1.0)
    response_time: float = Field(ge=3.0, le=12.0)
    min_rider_rating: float = Field(ge=1.0, le=5.0)
    surge_acceptance_modifier: float = Field(ge=1.0, le=2.0)

    # Profile attributes (mutable via profile events)
    home_location: tuple[float, float]
    preferred_zones: list[str]
    shift_preference: ShiftPreference
    avg_hours_per_day: int
    avg_days_per_week: int
    vehicle_make: str
    vehicle_model: str
    vehicle_year: int
    license_plate: str
    first_name: str
    last_name: str
    email: str
    phone: str

    @field_validator("home_location")
    @classmethod
    def validate_home_location(cls, v: tuple[float, float]) -> tuple[float, float]:
        return validate_sao_paulo_coordinates(v)


class RiderDNA(BaseModel):
    """Rider behavioral and profile DNA."""

    # Behavioral parameters (immutable)
    behavior_factor: float = Field(ge=0.0, le=1.0)
    patience_threshold: int = Field(ge=120, le=300)
    max_surge_multiplier: float = Field(ge=1.0)
    avg_rides_per_week: int
    frequent_destinations: list[dict[str, Any]] = Field(min_length=2, max_length=5)

    # Profile attributes (mutable via profile events)
    home_location: tuple[float, float]
    first_name: str
    last_name: str
    email: str
    phone: str
    payment_method_type: str
    payment_method_masked: str

    @field_validator("home_location")
    @classmethod
    def validate_home_location(cls, v: tuple[float, float]) -> tuple[float, float]:
        return validate_sao_paulo_coordinates(v)

    @field_validator("frequent_destinations")
    @classmethod
    def validate_destinations_distance(
        cls, v: list[dict[str, Any]], info: Any
    ) -> list[dict[str, Any]]:
        """Validate destinations are within 20km of home."""
        home_location = info.data.get("home_location")
        if not home_location:
            return v

        home_lat, home_lon = home_location
        for dest in v:
            dest_lat, dest_lon = dest["coordinates"]
            distance = haversine_distance(home_lat, home_lon, dest_lat, dest_lon)
            if distance > 20.0:
                raise ValueError(
                    f"Destination {dest['coordinates']} is {distance:.1f}km from home (max 20km)"
                )

        return v
