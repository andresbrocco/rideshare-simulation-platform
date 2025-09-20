from typing import Any

from pydantic import BaseModel, Field


class DriverCreateRequest(BaseModel):
    count: int = Field(..., ge=1, le=100)


class RiderCreateRequest(BaseModel):
    count: int = Field(..., ge=1, le=2000)


class DriversCreateResponse(BaseModel):
    created: int
    driver_ids: list[str]


class RidersCreateResponse(BaseModel):
    created: int
    rider_ids: list[str]


# --- DNA Override Models (for puppet agents) ---


class DriverDNAOverride(BaseModel):
    """Partial driver DNA for overriding specific fields."""

    # Behavioral parameters
    acceptance_rate: float | None = Field(None, ge=0.0, le=1.0)
    cancellation_tendency: float | None = Field(None, ge=0.0, le=1.0)
    service_quality: float | None = Field(None, ge=0.0, le=1.0)
    response_time: float | None = Field(None, ge=3.0, le=12.0)
    min_rider_rating: float | None = Field(None, ge=1.0, le=5.0)
    surge_acceptance_modifier: float | None = Field(None, ge=1.0, le=2.0)

    # Location (lat, lon)
    home_location: tuple[float, float] | None = None

    # Zone-based placement (alternative to home_location)
    zone_id: str | None = None


class RiderDNAOverride(BaseModel):
    """Partial rider DNA for overriding specific fields."""

    # Behavioral parameters
    behavior_factor: float | None = Field(None, ge=0.0, le=1.0)
    patience_threshold: int | None = Field(None, ge=120, le=300)
    max_surge_multiplier: float | None = Field(None, ge=1.0)
    avg_rides_per_week: int | None = Field(None, ge=1)

    # Location (lat, lon)
    home_location: tuple[float, float] | None = None

    # Zone-based placement (alternative to home_location)
    zone_id: str | None = None


class PuppetDriverCreateRequest(BaseModel):
    """Request to create puppet driver(s) with optional DNA overrides."""

    count: int = Field(1, ge=1, le=100)
    dna_override: DriverDNAOverride | None = None
    ephemeral: bool = True


class PuppetRiderCreateRequest(BaseModel):
    """Request to create puppet rider(s) with optional DNA overrides."""

    count: int = Field(1, ge=1, le=100)
    dna_override: RiderDNAOverride | None = None
    ephemeral: bool = True


# --- Agent State Response Models ---


class DriverDNAResponse(BaseModel):
    """Full driver DNA for API response."""

    # Behavioral
    acceptance_rate: float
    cancellation_tendency: float
    service_quality: float
    response_time: float
    min_rider_rating: float
    surge_acceptance_modifier: float

    # Location/Schedule
    home_location: tuple[float, float]
    preferred_zones: list[str]
    shift_preference: str
    avg_hours_per_day: int
    avg_days_per_week: int

    # Vehicle
    vehicle_make: str
    vehicle_model: str
    vehicle_year: int
    license_plate: str

    # Profile
    first_name: str
    last_name: str
    email: str
    phone: str


class RiderDNAResponse(BaseModel):
    """Full rider DNA for API response."""

    # Behavioral
    behavior_factor: float
    patience_threshold: int
    max_surge_multiplier: float
    avg_rides_per_week: int
    frequent_destinations: list[dict[str, Any]]

    # Location
    home_location: tuple[float, float]

    # Profile
    first_name: str
    last_name: str
    email: str
    phone: str
    payment_method_type: str
    payment_method_masked: str


class ActiveTripInfo(BaseModel):
    """Summary of an active trip."""

    trip_id: str
    state: str
    rider_id: str | None = None
    driver_id: str | None = None
    counterpart_name: str | None = (
        None  # Rider name (for driver) or driver name (for rider)
    )
    pickup_location: tuple[float, float]
    dropoff_location: tuple[float, float]
    surge_multiplier: float
    fare: float


class PendingOfferInfo(BaseModel):
    """Info about a pending offer for a puppet driver."""

    trip_id: str
    surge_multiplier: float
    rider_rating: float
    eta_seconds: int


class NextActionResponse(BaseModel):
    """Scheduled next action for an autonomous agent."""

    action_type: str
    scheduled_at: float  # Simulation time (env.now)
    scheduled_at_iso: str  # Human-readable ISO timestamp
    description: str


class DriverStatisticsResponse(BaseModel):
    """Session statistics for a driver."""

    # Trip statistics
    trips_completed: int
    trips_cancelled: int
    cancellation_rate: float

    # Offer statistics
    offers_received: int
    offers_accepted: int
    offers_rejected: int
    offers_expired: int
    acceptance_rate: float

    # Earnings (BRL)
    total_earnings: float
    avg_fare: float

    # Performance metrics
    avg_pickup_time_seconds: float
    avg_trip_duration_minutes: float
    avg_rating_given: float


class RiderStatisticsResponse(BaseModel):
    """Session statistics for a rider."""

    # Trip statistics
    trips_completed: int
    trips_cancelled: int
    trips_requested: int
    cancellation_rate: float
    requests_timed_out: int

    # Spending (BRL)
    total_spent: float
    avg_fare: float

    # Wait time metrics
    avg_wait_time_seconds: float
    avg_pickup_wait_seconds: float

    # Behavior metrics
    avg_rating_given: float
    surge_trips_percentage: float


class DriverStateResponse(BaseModel):
    """Full driver state for inspection."""

    driver_id: str
    status: str
    location: tuple[float, float] | None
    current_rating: float
    rating_count: int
    active_trip: ActiveTripInfo | None
    pending_offer: PendingOfferInfo | None = None
    next_action: NextActionResponse | None = None
    zone_id: str | None
    dna: DriverDNAResponse
    statistics: DriverStatisticsResponse
    is_ephemeral: bool
    is_puppet: bool


class RiderStateResponse(BaseModel):
    """Full rider state for inspection."""

    rider_id: str
    status: str
    location: tuple[float, float] | None
    current_rating: float
    rating_count: int
    active_trip: ActiveTripInfo | None
    next_action: NextActionResponse | None = None
    zone_id: str | None
    dna: RiderDNAResponse
    statistics: RiderStatisticsResponse
    is_ephemeral: bool
    is_puppet: bool


# --- Agent Control Models ---


class DriverStatusToggleRequest(BaseModel):
    """Request to toggle driver online/offline status."""

    go_online: bool = Field(..., description="True to go online, False to go offline")


class DriverStatusToggleResponse(BaseModel):
    """Response for driver status toggle."""

    driver_id: str
    previous_status: str
    new_status: str


class RiderTripRequestBody(BaseModel):
    """Request body for rider trip request."""

    destination: tuple[float, float] = Field(..., description="(lat, lon) destination")


class RiderTripRequestResponse(BaseModel):
    """Response for rider trip request."""

    rider_id: str
    trip_id: str
    pickup_location: tuple[float, float]
    destination: tuple[float, float]
    surge_multiplier: float
    estimated_fare: float
