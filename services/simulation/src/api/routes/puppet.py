"""Puppet agent API routes - manually controlled agents for testing."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from agents.dna import haversine_distance
from api.auth import verify_api_key
from api.models.puppet import (
    LocationUpdateRequest,
    PuppetActionResponse,
    PuppetDriverCreateResponse,
    PuppetDriveResponse,
    PuppetDriverWithDNARequest,
    PuppetRiderCreateResponse,
    PuppetRiderWithDNARequest,
    PuppetTripRequestBody,
    PuppetTripRequestResponse,
    RatingUpdateRequest,
)

router = APIRouter(prefix="/puppet", dependencies=[Depends(verify_api_key)])


# --- Dependency Getters ---


def get_agent_factory(request: Request) -> Any:
    return request.app.state.agent_factory


def get_simulation_engine(request: Request) -> Any:
    return request.app.state.simulation_engine


def get_zone_loader(request: Request) -> Any:
    return request.app.state.zone_loader


def get_matching_server(request: Request) -> Any:
    return request.app.state.matching_server


AgentFactoryDep = Annotated[Any, Depends(get_agent_factory)]
SimulationEngineDep = Annotated[Any, Depends(get_simulation_engine)]
ZoneLoaderDep = Annotated[Any, Depends(get_zone_loader)]
MatchingServerDep = Annotated[Any, Depends(get_matching_server)]


# --- Puppet Agent Creation ---


@router.post("/drivers", response_model=PuppetDriverCreateResponse)
def create_puppet_driver(
    request: PuppetDriverWithDNARequest,
    agent_factory: AgentFactoryDep,
) -> PuppetDriverCreateResponse:
    """Create a puppet driver at the specified location.

    Puppet drivers:
    - Start in 'offline' status
    - Emit GPS pings but take no autonomous actions
    - All state transitions triggered via API
    - Support optional DNA overrides for testing specific behaviors
    """
    try:
        override_dict = (
            request.dna_override.model_dump(exclude_none=True) if request.dna_override else None
        )
        zone_id = request.dna_override.zone_id if request.dna_override else None

        driver_id = agent_factory.create_puppet_driver(
            location=request.location,
            dna_override=override_dict,
            zone_id=zone_id,
            ephemeral=request.ephemeral,
        )
        return PuppetDriverCreateResponse(
            driver_id=driver_id,
            location=request.location,
            status="offline",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/riders", response_model=PuppetRiderCreateResponse)
def create_puppet_rider(
    request: PuppetRiderWithDNARequest,
    agent_factory: AgentFactoryDep,
) -> PuppetRiderCreateResponse:
    """Create a puppet rider at the specified location.

    Puppet riders:
    - Start in 'offline' status
    - Emit GPS pings but take no autonomous actions
    - All state transitions triggered via API
    - Support optional DNA overrides for testing specific behaviors
    """
    try:
        override_dict = (
            request.dna_override.model_dump(exclude_none=True) if request.dna_override else None
        )
        zone_id = request.dna_override.zone_id if request.dna_override else None

        rider_id = agent_factory.create_puppet_rider(
            location=request.location,
            dna_override=override_dict,
            zone_id=zone_id,
            ephemeral=request.ephemeral,
        )
        return PuppetRiderCreateResponse(
            rider_id=rider_id,
            location=request.location,
            status="offline",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# --- Driver Control Endpoints ---


@router.put("/drivers/{driver_id}/go-online", response_model=PuppetActionResponse)
def puppet_driver_go_online(
    driver_id: str,
    engine: SimulationEngineDep,
) -> PuppetActionResponse:
    """Set puppet driver status to online.

    Valid from: offline
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    if driver.status != "offline":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot go online from status '{driver.status}'. Must be 'offline'.",
        )

    driver.go_online()

    return PuppetActionResponse(
        success=True,
        message="Driver is now online",
        agent_id=driver_id,
        new_status=driver.status,
    )


@router.put("/drivers/{driver_id}/go-offline", response_model=PuppetActionResponse)
def puppet_driver_go_offline(
    driver_id: str,
    engine: SimulationEngineDep,
) -> PuppetActionResponse:
    """Set puppet driver status to offline.

    Valid from: online (with no active trip)
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    if driver.status != "online":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot go offline from status '{driver.status}'. Must be 'online'.",
        )

    if driver.active_trip:
        raise HTTPException(
            status_code=400,
            detail="Cannot go offline while driver has active trip",
        )

    driver.go_offline()

    return PuppetActionResponse(
        success=True,
        message="Driver is now offline",
        agent_id=driver_id,
        new_status=driver.status,
    )


@router.post("/drivers/{driver_id}/accept-offer", response_model=PuppetActionResponse)
def puppet_driver_accept_offer(
    driver_id: str,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetActionResponse:
    """Accept the pending trip offer for this driver.

    Valid from: online (with pending offer)
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    if driver.status != "online":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot accept offer from status '{driver.status}'. Must be 'online'.",
        )

    # Get pending offer from matching server
    pending_offer = matching_server.get_pending_offer_for_driver(driver_id)
    if not pending_offer:
        raise HTTPException(
            status_code=400,
            detail="No pending offer for this driver",
        )

    # Accept the offer
    matching_server.process_puppet_accept(driver_id, pending_offer["trip_id"])

    return PuppetActionResponse(
        success=True,
        message=f"Accepted trip {pending_offer['trip_id']}",
        agent_id=driver_id,
        new_status=driver.status,
    )


@router.post("/drivers/{driver_id}/reject-offer", response_model=PuppetActionResponse)
def puppet_driver_reject_offer(
    driver_id: str,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetActionResponse:
    """Reject the pending trip offer for this driver.

    Valid from: online (with pending offer)
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    if driver.status != "online":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject offer from status '{driver.status}'. Must be 'online'.",
        )

    # Get pending offer from matching server
    pending_offer = matching_server.get_pending_offer_for_driver(driver_id)
    if not pending_offer:
        raise HTTPException(
            status_code=400,
            detail="No pending offer for this driver",
        )

    # Reject the offer
    matching_server.process_puppet_reject(driver_id, pending_offer["trip_id"])

    return PuppetActionResponse(
        success=True,
        message=f"Rejected trip {pending_offer['trip_id']}",
        agent_id=driver_id,
        new_status=driver.status,
    )


@router.post("/drivers/{driver_id}/drive-to-pickup", response_model=PuppetDriveResponse)
def puppet_driver_drive_to_pickup(
    driver_id: str,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetDriveResponse:
    """Start driving the puppet driver to the pickup location.

    Prerequisites:
    - Driver must have accepted an offer (status: en_route_pickup)
    - Trip must be in DRIVER_EN_ROUTE state

    This endpoint returns immediately. The driver will move along the
    OSRM route in the background, emitting GPS updates at regular intervals.
    Use the WebSocket or GET /agents/drivers/{id} to monitor progress.
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    if driver.status != "en_route_pickup":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot drive to pickup from status '{driver.status}'. "
            "Must be 'en_route_pickup'. Call accept-offer first.",
        )

    if not driver.active_trip:
        raise HTTPException(status_code=400, detail="No active trip for this driver")

    try:
        route, _controller = matching_server.start_puppet_drive_to_pickup(
            driver_id, driver.active_trip
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return PuppetDriveResponse(
        success=True,
        message="Driver is now driving to pickup location",
        driver_id=driver_id,
        trip_id=driver.active_trip,
        new_status=driver.status,
        route=route.geometry,
        distance_meters=route.distance_meters,
        estimated_duration_seconds=route.duration_seconds,
    )


@router.post("/drivers/{driver_id}/drive-to-destination", response_model=PuppetDriveResponse)
def puppet_driver_drive_to_destination(
    driver_id: str,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetDriveResponse:
    """Start driving the puppet driver to the destination.

    Prerequisites:
    - Driver must have started the trip (status: en_route_destination)
    - Trip must be in STARTED state

    This endpoint returns immediately. The driver will move along the
    OSRM route in the background, emitting GPS updates at regular intervals.
    Use the WebSocket or GET /agents/drivers/{id} to monitor progress.
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    if driver.status != "en_route_destination":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot drive to destination from status '{driver.status}'. "
            "Must be 'en_route_destination'. Call start-trip first.",
        )

    if not driver.active_trip:
        raise HTTPException(status_code=400, detail="No active trip for this driver")

    try:
        route, _controller = matching_server.start_puppet_drive_to_destination(
            driver_id, driver.active_trip
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return PuppetDriveResponse(
        success=True,
        message="Driver is now driving to destination",
        driver_id=driver_id,
        trip_id=driver.active_trip,
        new_status=driver.status,
        route=route.geometry,
        distance_meters=route.distance_meters,
        estimated_duration_seconds=route.duration_seconds,
    )


@router.post("/drivers/{driver_id}/arrive-pickup", response_model=PuppetActionResponse)
def puppet_driver_arrive_pickup(
    driver_id: str,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetActionResponse:
    """Signal that driver has arrived at pickup location.

    Valid from: en_route_pickup
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    if driver.status != "en_route_pickup":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot arrive at pickup from status '{driver.status}'. "
            "Must be 'en_route_pickup'.",
        )

    if not driver.active_trip:
        raise HTTPException(status_code=400, detail="No active trip for this driver")

    matching_server.signal_driver_arrived(driver_id, driver.active_trip)

    return PuppetActionResponse(
        success=True,
        message="Driver arrived at pickup location",
        agent_id=driver_id,
        new_status=driver.status,
    )


@router.post("/drivers/{driver_id}/start-trip", response_model=PuppetActionResponse)
def puppet_driver_start_trip(
    driver_id: str,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetActionResponse:
    """Signal that rider has been picked up and trip is starting.

    Valid from: en_route_pickup (after arrive-pickup)
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    if driver.status != "en_route_pickup":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start trip from status '{driver.status}'. Must be 'en_route_pickup'.",
        )

    if not driver.active_trip:
        raise HTTPException(status_code=400, detail="No active trip for this driver")

    matching_server.signal_trip_started(driver_id, driver.active_trip)

    return PuppetActionResponse(
        success=True,
        message="Trip started - rider picked up",
        agent_id=driver_id,
        new_status=driver.status,
    )


@router.post("/drivers/{driver_id}/complete-trip", response_model=PuppetActionResponse)
def puppet_driver_complete_trip(
    driver_id: str,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetActionResponse:
    """Signal that trip has been completed at destination.

    Valid from: en_route_destination (after start-trip)
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    if driver.status != "en_route_destination":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot complete trip from status '{driver.status}'. "
            "Must be 'en_route_destination'.",
        )

    if not driver.active_trip:
        raise HTTPException(status_code=400, detail="No active trip for this driver")

    matching_server.signal_trip_completed(driver_id, driver.active_trip)

    return PuppetActionResponse(
        success=True,
        message="Trip completed",
        agent_id=driver_id,
        new_status=driver.status,
    )


@router.post("/drivers/{driver_id}/cancel-trip", response_model=PuppetActionResponse)
def puppet_driver_cancel_trip(
    driver_id: str,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetActionResponse:
    """Cancel the current trip (before pickup only).

    Valid from: en_route_pickup
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    if driver.status != "en_route_pickup":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel trip from status '{driver.status}'. "
            "Must be 'en_route_pickup'.",
        )

    if not driver.active_trip:
        raise HTTPException(status_code=400, detail="No active trip for this driver")

    matching_server.cancel_trip(
        driver.active_trip, cancelled_by="driver", reason="Puppet driver cancelled"
    )

    return PuppetActionResponse(
        success=True,
        message="Trip cancelled",
        agent_id=driver_id,
        new_status=driver.status,
    )


# --- Rider Control Endpoints ---


@router.post("/riders/{rider_id}/request-trip", response_model=PuppetTripRequestResponse)
async def puppet_rider_request_trip(
    rider_id: str,
    body: PuppetTripRequestBody,
    engine: SimulationEngineDep,
    zone_loader: ZoneLoaderDep,
    matching_server: MatchingServerDep,
) -> PuppetTripRequestResponse:
    """Request a trip for the puppet rider.

    Valid from: offline
    """
    rider = engine._active_riders.get(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail=f"Rider {rider_id} not found")

    if not getattr(rider, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet rider")

    if rider.status != "offline":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot request trip from status '{rider.status}'. Must be 'offline'.",
        )

    if not rider.location:
        raise HTTPException(status_code=400, detail="Rider location not available")

    trip_id = str(uuid.uuid4())

    # Determine zones
    pickup_zone_id = (
        zone_loader.find_zone_for_location(rider.location[0], rider.location[1])
        if zone_loader
        else "unknown"
    ) or "unknown"
    dropoff_zone_id = (
        zone_loader.find_zone_for_location(body.destination[0], body.destination[1])
        if zone_loader
        else "unknown"
    ) or "unknown"

    # Get surge for pickup zone
    surge_multiplier = 1.0
    if matching_server._surge_calculator:
        surge_multiplier = matching_server._surge_calculator.get_surge(pickup_zone_id)

    # Calculate fare estimate
    distance_km = haversine_distance(
        rider.location[0],
        rider.location[1],
        body.destination[0],
        body.destination[1],
    )
    base_fare = 5.0
    per_km_rate = 2.5
    fare = (base_fare + (distance_km * per_km_rate)) * surge_multiplier

    # Request match via matching server (async call)
    await matching_server.request_match(
        rider_id=rider_id,
        pickup_location=rider.location,
        dropoff_location=body.destination,
        pickup_zone_id=pickup_zone_id,
        dropoff_zone_id=dropoff_zone_id,
        surge_multiplier=surge_multiplier,
        fare=round(fare, 2),
        trip_id=trip_id,
    )

    # Update rider state to waiting with active trip
    rider.request_trip(trip_id)

    return PuppetTripRequestResponse(
        rider_id=rider_id,
        trip_id=trip_id,
        pickup_location=rider.location,
        destination=body.destination,
        surge_multiplier=surge_multiplier,
        estimated_fare=round(fare, 2),
    )


@router.post("/riders/{rider_id}/cancel-trip", response_model=PuppetActionResponse)
def puppet_rider_cancel_trip(
    rider_id: str,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetActionResponse:
    """Cancel the pending trip request.

    Valid from: waiting
    """
    rider = engine._active_riders.get(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail=f"Rider {rider_id} not found")

    if not getattr(rider, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet rider")

    if rider.status != "waiting":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel trip from status '{rider.status}'. Must be 'waiting'.",
        )

    if not rider.active_trip:
        raise HTTPException(status_code=400, detail="No active trip for this rider")

    matching_server.cancel_trip(
        rider.active_trip, cancelled_by="rider", reason="Puppet rider cancelled"
    )

    return PuppetActionResponse(
        success=True,
        message="Trip cancelled",
        agent_id=rider_id,
        new_status=rider.status,
    )


# --- Testing Control Endpoints ---


@router.put("/drivers/{driver_id}/rating", response_model=PuppetActionResponse)
def update_driver_rating(
    driver_id: str,
    body: RatingUpdateRequest,
    engine: SimulationEngineDep,
) -> PuppetActionResponse:
    """Update a puppet driver's rating for testing.

    Allows testing driver acceptance thresholds and rating-based matching.
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    old_rating = driver.current_rating
    driver._current_rating = body.rating
    driver._rating_count = max(driver._rating_count, 1)  # Ensure at least 1 rating

    return PuppetActionResponse(
        success=True,
        message=f"Rating updated from {old_rating:.2f} to {body.rating:.2f}",
        agent_id=driver_id,
        new_status=driver.status,
    )


@router.put("/riders/{rider_id}/rating", response_model=PuppetActionResponse)
def update_rider_rating(
    rider_id: str,
    body: RatingUpdateRequest,
    engine: SimulationEngineDep,
) -> PuppetActionResponse:
    """Update a puppet rider's rating for testing.

    Allows testing driver acceptance based on rider rating thresholds.
    """
    rider = engine._active_riders.get(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail=f"Rider {rider_id} not found")

    if not getattr(rider, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet rider")

    old_rating = rider.current_rating
    rider._current_rating = body.rating
    rider._rating_count = max(rider._rating_count, 1)

    return PuppetActionResponse(
        success=True,
        message=f"Rating updated from {old_rating:.2f} to {body.rating:.2f}",
        agent_id=rider_id,
        new_status=rider.status,
    )


@router.put("/drivers/{driver_id}/location", response_model=PuppetActionResponse)
def teleport_driver(
    driver_id: str,
    body: LocationUpdateRequest,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetActionResponse:
    """Teleport a puppet driver to a new location.

    Useful for testing geospatial matching logic.
    Constraint: Cannot teleport while in active trip.
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    if driver.active_trip:
        raise HTTPException(
            status_code=400,
            detail="Cannot teleport driver during active trip",
        )

    old_location = driver.location
    driver._location = body.location

    # Update geospatial index if driver is online
    if driver.status == "online" and matching_server:
        matching_server._driver_index.update_driver_location(driver.driver_id, body.location)

    return PuppetActionResponse(
        success=True,
        message=f"Teleported from {old_location} to {body.location}",
        agent_id=driver_id,
        new_status=driver.status,
    )


@router.put("/riders/{rider_id}/location", response_model=PuppetActionResponse)
def teleport_rider(
    rider_id: str,
    body: LocationUpdateRequest,
    engine: SimulationEngineDep,
) -> PuppetActionResponse:
    """Teleport a puppet rider to a new location.

    Useful for testing zone-based surge pricing and matching.
    Constraint: Cannot teleport while in active trip.
    """
    rider = engine._active_riders.get(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail=f"Rider {rider_id} not found")

    if not getattr(rider, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet rider")

    if rider.active_trip:
        raise HTTPException(
            status_code=400,
            detail="Cannot teleport rider during active trip",
        )

    old_location = rider.location
    rider._location = body.location

    return PuppetActionResponse(
        success=True,
        message=f"Teleported from {old_location} to {body.location}",
        agent_id=rider_id,
        new_status=rider.status,
    )


@router.post("/drivers/{driver_id}/force-offer-timeout", response_model=PuppetActionResponse)
def force_driver_offer_timeout(
    driver_id: str,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetActionResponse:
    """Force a pending offer to timeout.

    Simulates offer expiry without waiting for actual timeout.
    Valid from: online with pending offer
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if not getattr(driver, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet driver")

    pending_offer = matching_server.get_pending_offer_for_driver(driver_id)
    if not pending_offer:
        raise HTTPException(
            status_code=400,
            detail="No pending offer to timeout",
        )

    trip_id = pending_offer["trip_id"]
    # Process as timeout (increments offers_expired, not offers_rejected)
    matching_server.process_puppet_timeout(driver_id, trip_id)

    return PuppetActionResponse(
        success=True,
        message="Offer timed out (forced)",
        agent_id=driver_id,
        new_status=driver.status,
    )


@router.post("/riders/{rider_id}/force-patience-timeout", response_model=PuppetActionResponse)
def force_rider_patience_timeout(
    rider_id: str,
    engine: SimulationEngineDep,
    matching_server: MatchingServerDep,
) -> PuppetActionResponse:
    """Force the rider to timeout waiting.

    Simulates patience expiry without waiting for actual timeout.
    Valid from: waiting
    """
    rider = engine._active_riders.get(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail=f"Rider {rider_id} not found")

    if not getattr(rider, "_is_puppet", False):
        raise HTTPException(status_code=400, detail="Agent is not a puppet rider")

    if rider.status != "waiting":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot force timeout from status '{rider.status}'. Must be 'waiting'.",
        )

    if not rider.active_trip:
        raise HTTPException(status_code=400, detail="No active trip for this rider")

    matching_server.cancel_trip(rider.active_trip, cancelled_by="rider", reason="patience_timeout")

    return PuppetActionResponse(
        success=True,
        message="Patience timeout forced",
        agent_id=rider_id,
        new_status=rider.status,
    )
