"""Request/response models for puppet agent endpoints."""

from pydantic import BaseModel, Field

from api.models.agents import DriverDNAOverride, RiderDNAOverride


class PuppetAgentCreateRequest(BaseModel):
    """Request to create a puppet agent (simple location-based)."""

    location: tuple[float, float] = Field(
        ..., description="Initial location (lat, lon) for the puppet agent"
    )


class PuppetDriverWithDNARequest(BaseModel):
    """Request to create a puppet driver with optional DNA overrides."""

    location: tuple[float, float] = Field(
        ..., description="Initial location (lat, lon) for the puppet driver"
    )
    dna_override: DriverDNAOverride | None = Field(None, description="Optional DNA override fields")
    ephemeral: bool = Field(True, description="If True, skip SQLite persistence")


class PuppetRiderWithDNARequest(BaseModel):
    """Request to create a puppet rider with optional DNA overrides."""

    location: tuple[float, float] = Field(
        ..., description="Initial location (lat, lon) for the puppet rider"
    )
    dna_override: RiderDNAOverride | None = Field(None, description="Optional DNA override fields")
    ephemeral: bool = Field(True, description="If True, skip SQLite persistence")


class PuppetDriverCreateResponse(BaseModel):
    """Response for creating a puppet driver."""

    driver_id: str
    location: tuple[float, float]
    status: str = "offline"


class PuppetRiderCreateResponse(BaseModel):
    """Response for creating a puppet rider."""

    rider_id: str
    location: tuple[float, float]
    status: str = "offline"


class PuppetActionResponse(BaseModel):
    """Generic response for puppet agent actions."""

    success: bool
    message: str
    agent_id: str
    new_status: str | None = None


class PuppetTripRequestBody(BaseModel):
    """Request body for puppet rider trip request."""

    destination: tuple[float, float] = Field(..., description="Destination coordinates (lat, lon)")


class PuppetTripRequestResponse(BaseModel):
    """Response for puppet rider trip request."""

    rider_id: str
    trip_id: str
    pickup_location: tuple[float, float]
    destination: tuple[float, float]
    surge_multiplier: float
    estimated_fare: float


# --- Testing Control Models ---


class RatingUpdateRequest(BaseModel):
    """Request to update an agent's rating."""

    rating: float = Field(..., ge=1.0, le=5.0, description="New rating (1.0-5.0)")


class LocationUpdateRequest(BaseModel):
    """Request to teleport an agent to a new location."""

    location: tuple[float, float] = Field(..., description="New location (lat, lon)")


class PuppetDriveResponse(BaseModel):
    """Response for puppet drive endpoints (drive-to-pickup, drive-to-destination)."""

    success: bool
    message: str
    driver_id: str
    trip_id: str
    new_status: str
    route: list[tuple[float, float]] = Field(..., description="Route geometry for visualization")
    distance_meters: float
    estimated_duration_seconds: float
