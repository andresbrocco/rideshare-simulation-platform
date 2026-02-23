from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CorrelationMixin(BaseModel):
    """Mixin adding distributed tracing fields to events."""

    session_id: str | None = Field(default=None, description="Simulation run identifier")
    correlation_id: str | None = Field(
        default=None, description="Primary correlation ID (e.g., trip_id)"
    )
    causation_id: str | None = Field(default=None, description="ID of event that caused this one")


class TripEvent(CorrelationMixin):
    """Event for trip state transitions"""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: Literal[
        "trip.requested",
        "trip.offer_sent",
        "trip.driver_assigned",
        "trip.en_route_pickup",
        "trip.at_pickup",
        "trip.in_transit",
        "trip.completed",
        "trip.cancelled",
        "trip.offer_expired",
        "trip.offer_rejected",
        "trip.no_drivers_available",
    ]
    trip_id: str
    timestamp: str
    rider_id: str
    driver_id: str | None
    pickup_location: tuple[float, float]
    dropoff_location: tuple[float, float]
    pickup_zone_id: str
    dropoff_zone_id: str
    surge_multiplier: float
    fare: float
    offer_sequence: int | None = None
    cancelled_by: str | None = None
    cancellation_reason: str | None = None
    cancellation_stage: str | None = None
    # Route data for frontend visualization
    route: list[tuple[float, float]] | None = None
    pickup_route: list[tuple[float, float]] | None = None
    # Route progress indices for efficient updates (index into route geometry)
    route_progress_index: int | None = None
    pickup_route_progress_index: int | None = None


class GPSPingEvent(CorrelationMixin):
    """GPS location ping from driver or rider"""

    event_id: UUID = Field(default_factory=uuid4)
    entity_type: Literal["driver", "rider"]
    entity_id: str
    timestamp: str
    location: tuple[float, float]
    heading: float | None
    speed: float | None
    accuracy: float
    trip_id: str | None
    trip_state: str | None = None  # For rider GPS pings during active trips
    # Route progress indices for frontend visualization
    route_progress_index: int | None = None
    pickup_route_progress_index: int | None = None


class DriverStatusEvent(CorrelationMixin):
    """Driver status change event"""

    event_id: UUID = Field(default_factory=uuid4)
    driver_id: str
    timestamp: str
    previous_status: str | None
    new_status: Literal[
        "available", "offline", "en_route_pickup", "on_trip", "driving_closer_to_home"
    ]
    trigger: str
    location: tuple[float, float]


class SurgeUpdateEvent(CorrelationMixin):
    """Surge pricing update for a zone"""

    event_id: UUID = Field(default_factory=uuid4)
    zone_id: str
    timestamp: str
    previous_multiplier: float
    new_multiplier: float
    available_drivers: int
    pending_requests: int
    calculation_window_seconds: int = 60


class RatingEvent(CorrelationMixin):
    """Rating submitted after trip completion"""

    event_id: UUID = Field(default_factory=uuid4)
    trip_id: str
    timestamp: str
    rater_type: Literal["rider", "driver"]
    rater_id: str
    ratee_type: Literal["rider", "driver"]
    ratee_id: str
    rating: int = Field(ge=1, le=5)
    current_rating: float  # Rolling average after this rating
    rating_count: int  # Total ratings after this rating


class PaymentEvent(CorrelationMixin):
    """Payment processing event"""

    event_id: UUID = Field(default_factory=uuid4)
    payment_id: str
    trip_id: str
    timestamp: str
    rider_id: str
    driver_id: str
    payment_method_type: Literal["credit_card", "digital_wallet"]
    payment_method_masked: str
    fare_amount: float
    platform_fee_percentage: float
    platform_fee_amount: float
    driver_payout_amount: float


class DriverProfileEvent(CorrelationMixin):
    """Driver profile creation or update"""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: Literal["driver.created", "driver.updated"]
    driver_id: str
    timestamp: str
    first_name: str
    last_name: str
    email: str
    phone: str
    home_location: tuple[float, float]
    shift_preference: Literal["morning", "afternoon", "evening", "night", "flexible"]
    vehicle_make: str
    vehicle_model: str
    vehicle_year: int
    license_plate: str


class RiderProfileEvent(CorrelationMixin):
    """Rider profile creation or update"""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: Literal["rider.created", "rider.updated"]
    rider_id: str
    timestamp: str
    first_name: str
    last_name: str
    email: str
    phone: str
    home_location: tuple[float, float]
    payment_method_type: Literal["credit_card", "digital_wallet"]
    payment_method_masked: str
    behavior_factor: float | None = None
