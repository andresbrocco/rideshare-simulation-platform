"""Pydantic models for API requests and responses."""

from api.models.agents import (
    ActiveTripInfo,
    DriverCreateRequest,
    DriverDNAOverride,
    DriverDNAResponse,
    DriversCreateResponse,
    DriverStateResponse,
    DriverStatusToggleRequest,
    DriverStatusToggleResponse,
    PuppetDriverCreateRequest,
    PuppetRiderCreateRequest,
    RiderCreateRequest,
    RiderDNAOverride,
    RiderDNAResponse,
    RidersCreateResponse,
    RiderStateResponse,
    RiderTripRequestBody,
    RiderTripRequestResponse,
)
from api.models.health import DetailedHealthResponse, ServiceHealth
from api.models.metrics import DriverMetrics, OverviewMetrics, TripMetrics, ZoneMetrics
from api.models.simulation import (
    ControlResponse,
    SimulationStatusResponse,
    SpeedChangeRequest,
    SpeedChangeResponse,
)

__all__ = [
    # Health models
    "DetailedHealthResponse",
    "ServiceHealth",
    # Agent models
    "DriverCreateRequest",
    "RiderCreateRequest",
    "DriversCreateResponse",
    "RidersCreateResponse",
    # Puppet agent models
    "DriverDNAOverride",
    "RiderDNAOverride",
    "PuppetDriverCreateRequest",
    "PuppetRiderCreateRequest",
    # Agent state models
    "ActiveTripInfo",
    "DriverDNAResponse",
    "RiderDNAResponse",
    "DriverStateResponse",
    "RiderStateResponse",
    # Agent control models
    "DriverStatusToggleRequest",
    "DriverStatusToggleResponse",
    "RiderTripRequestBody",
    "RiderTripRequestResponse",
    # Metrics models
    "DriverMetrics",
    "OverviewMetrics",
    "TripMetrics",
    "ZoneMetrics",
    # Simulation models
    "ControlResponse",
    "SimulationStatusResponse",
    "SpeedChangeRequest",
    "SpeedChangeResponse",
]
