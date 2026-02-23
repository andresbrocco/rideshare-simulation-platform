from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from api.auth import verify_api_key
from api.models.agents import (
    ActionHistoryEntryResponse,
    ActiveTripInfo,
    DriverCreateRequest,
    DriverDNAResponse,
    DriversCreateResponse,
    DriverStateResponse,
    DriverStatisticsResponse,
    DriverStatusToggleRequest,
    DriverStatusToggleResponse,
    NextActionResponse,
    PendingOfferInfo,
    RiderCreateRequest,
    RiderDNAResponse,
    RidersCreateResponse,
    RiderStateResponse,
    RiderStatisticsResponse,
    RiderTripRequestBody,
    RiderTripRequestResponse,
    SpawnMode,
    SpawnQueueStatusResponse,
)
from api.rate_limit import limiter
from settings import get_settings

router = APIRouter(dependencies=[Depends(verify_api_key)])


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


# --- Helper Functions ---


def compute_next_action_response(agent: Any, engine: Any) -> NextActionResponse | None:
    """Compute next action response for an autonomous agent.

    Converts simulation time to wall-clock ISO timestamp.
    Returns None for puppet agents or agents with no scheduled action.
    """
    if agent._is_puppet or agent.next_action is None:
        return None

    na = agent.next_action
    # Convert simulation time to wall-clock time using TimeManager
    scheduled_datetime = engine._time_manager.to_datetime(na.scheduled_at)

    return NextActionResponse(
        action_type=na.action_type.value,
        scheduled_at=na.scheduled_at,
        scheduled_at_iso=scheduled_datetime.isoformat(),
        description=na.description,
    )


def compute_action_history_response(agent: Any, engine: Any) -> list[ActionHistoryEntryResponse]:
    """Convert agent's in-memory action history to API response format.

    Returns entries in reverse chronological order (newest first).
    """
    return [
        ActionHistoryEntryResponse(
            action_type=entry.action_type,
            occurred_at_iso=engine._time_manager.to_datetime(entry.occurred_at).isoformat(),
        )
        for entry in reversed(agent._action_history)
    ]


# --- Standard Agent Creation ---


@router.post("/drivers", response_model=DriversCreateResponse)
@limiter.limit("120/minute")
def create_drivers(
    request: Request,
    body: DriverCreateRequest,
    agent_factory: AgentFactoryDep,
    mode: Annotated[
        SpawnMode,
        Query(
            description="immediate: go online immediately; scheduled: follow DNA shift_preference"
        ),
    ] = SpawnMode.IMMEDIATE,
) -> DriversCreateResponse:
    """Queue driver agents for continuous spawning.

    Drivers are spawned at a continuous rate (default: 2/sec) to prevent
    synchronized GPS ping bursts. Use GET /agents/spawn-status to monitor progress.

    Query Parameters:
        mode: immediate (default) - drivers go online immediately
              scheduled - drivers follow their DNA shift_preference schedule
    """
    try:
        settings = get_settings()
        immediate = mode == SpawnMode.IMMEDIATE
        queued = agent_factory.queue_drivers(body.count, immediate=immediate)
        spawn_rate = (
            settings.spawn.driver_immediate_spawn_rate
            if immediate
            else settings.spawn.driver_scheduled_spawn_rate
        )
        return DriversCreateResponse(
            queued=queued,
            spawn_rate=spawn_rate,
            estimated_completion_seconds=queued / spawn_rate,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/riders", response_model=RidersCreateResponse)
@limiter.limit("120/minute")
def create_riders(
    request: Request,
    body: RiderCreateRequest,
    agent_factory: AgentFactoryDep,
    mode: Annotated[
        SpawnMode,
        Query(
            description="immediate: request trip immediately; scheduled: follow DNA avg_rides_per_week"
        ),
    ] = SpawnMode.SCHEDULED,
) -> RidersCreateResponse:
    """Queue rider agents for continuous spawning.

    Riders are spawned at a continuous rate (default: 40/sec) to prevent
    synchronized GPS ping bursts. Use GET /agents/spawn-status to monitor progress.

    Query Parameters:
        mode: immediate - riders request a trip immediately after spawning
              scheduled (default) - riders follow their DNA avg_rides_per_week schedule
    """
    try:
        settings = get_settings()
        immediate = mode == SpawnMode.IMMEDIATE
        queued = agent_factory.queue_riders(body.count, immediate=immediate)
        spawn_rate = (
            settings.spawn.rider_immediate_spawn_rate
            if immediate
            else settings.spawn.rider_scheduled_spawn_rate
        )
        return RidersCreateResponse(
            queued=queued,
            spawn_rate=spawn_rate,
            estimated_completion_seconds=queued / spawn_rate,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/spawn-status", response_model=SpawnQueueStatusResponse)
@limiter.limit("60/minute")
def get_spawn_status(request: Request, agent_factory: AgentFactoryDep) -> SpawnQueueStatusResponse:
    """Get current spawn queue status.

    Returns the number of drivers and riders waiting to be spawned.
    """
    status = agent_factory.get_spawn_queue_status()
    return SpawnQueueStatusResponse(**status)


# --- Agent State Inspection ---


@router.get("/drivers/{driver_id}", response_model=DriverStateResponse)
@limiter.limit("60/minute")
def get_driver_state(
    request: Request,
    driver_id: str,
    engine: SimulationEngineDep,
    zone_loader: ZoneLoaderDep,
    matching_server: MatchingServerDep,
) -> DriverStateResponse:
    """Get full state and DNA for a driver.

    Returns the driver's current state (status, location, rating),
    active trip info if any, and complete DNA parameters.
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    # Get active trip info if any
    active_trip_info = None
    if driver.active_trip and matching_server:
        trip = matching_server._active_trips.get(driver.active_trip)
        if trip:
            # Get rider name as counterpart for driver
            counterpart_name = None
            if trip.rider_id:
                rider = engine._active_riders.get(trip.rider_id)
                if rider:
                    counterpart_name = f"{rider.dna.first_name} {rider.dna.last_name}"

            active_trip_info = ActiveTripInfo(
                trip_id=trip.trip_id,
                state=trip.state.value,
                rider_id=trip.rider_id,
                driver_id=trip.driver_id,
                counterpart_name=counterpart_name,
                pickup_location=trip.pickup_location,
                dropoff_location=trip.dropoff_location,
                surge_multiplier=trip.surge_multiplier,
                fare=trip.fare,
            )

    # Get pending offer for puppet drivers
    pending_offer_info = None
    if matching_server:
        pending_offer = matching_server.get_pending_offer_for_driver(driver_id)
        if pending_offer:
            pending_offer_info = PendingOfferInfo(
                trip_id=pending_offer["trip_id"],
                surge_multiplier=pending_offer["surge_multiplier"],
                rider_rating=pending_offer["rider_rating"],
                eta_seconds=pending_offer["eta_seconds"],
            )

    state = driver.get_state(zone_loader)
    dna = driver.dna
    stats = driver.statistics

    # Compute next action for autonomous agents
    next_action_info = compute_next_action_response(driver, engine)
    action_history = compute_action_history_response(driver, engine)

    return DriverStateResponse(
        driver_id=driver.driver_id,
        status=state["status"],
        location=state["location"],
        current_rating=state["current_rating"],
        rating_count=state["rating_count"],
        active_trip=active_trip_info,
        pending_offer=pending_offer_info,
        next_action=next_action_info,
        action_history=action_history,
        zone_id=state["zone_id"],
        is_ephemeral=state["is_ephemeral"],
        is_puppet=state["is_puppet"],
        dna=DriverDNAResponse(
            acceptance_rate=dna.acceptance_rate,
            cancellation_tendency=dna.cancellation_tendency,
            service_quality=dna.service_quality,
            avg_response_time=dna.avg_response_time,
            min_rider_rating=dna.min_rider_rating,
            surge_acceptance_modifier=dna.surge_acceptance_modifier,
            home_location=dna.home_location,
            shift_preference=dna.shift_preference.value,
            avg_hours_per_day=dna.avg_hours_per_day,
            avg_days_per_week=dna.avg_days_per_week,
            vehicle_make=dna.vehicle_make,
            vehicle_model=dna.vehicle_model,
            vehicle_year=dna.vehicle_year,
            license_plate=dna.license_plate,
            first_name=dna.first_name,
            last_name=dna.last_name,
            email=dna.email,
            phone=dna.phone,
        ),
        statistics=DriverStatisticsResponse(
            trips_completed=stats.trips_completed,
            trips_cancelled=stats.trips_cancelled,
            cancellation_rate=stats.cancellation_rate,
            offers_received=stats.offers_received,
            offers_accepted=stats.offers_accepted,
            offers_rejected=stats.offers_rejected,
            offers_expired=stats.offers_expired,
            acceptance_rate=stats.acceptance_rate,
            total_earnings=stats.total_earnings,
            avg_fare=stats.avg_fare,
            avg_pickup_time_seconds=stats.avg_pickup_time_seconds,
            avg_trip_duration_minutes=stats.avg_trip_duration_minutes,
            avg_rating_given=stats.avg_rating_given,
        ),
    )


@router.get("/riders/{rider_id}", response_model=RiderStateResponse)
@limiter.limit("60/minute")
def get_rider_state(
    request: Request,
    rider_id: str,
    engine: SimulationEngineDep,
    zone_loader: ZoneLoaderDep,
    matching_server: MatchingServerDep,
) -> RiderStateResponse:
    """Get full state and DNA for a rider.

    Returns the rider's current state (status, location, rating),
    active trip info if any, and complete DNA parameters.
    """
    rider = engine._active_riders.get(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail=f"Rider {rider_id} not found")

    # Get active trip info if any
    active_trip_info = None
    if rider.active_trip and matching_server:
        trip = matching_server._active_trips.get(rider.active_trip)
        if trip:
            # Get driver name as counterpart for rider
            counterpart_name = None
            if trip.driver_id:
                driver = engine._active_drivers.get(trip.driver_id)
                if driver:
                    counterpart_name = f"{driver.dna.first_name} {driver.dna.last_name}"

            active_trip_info = ActiveTripInfo(
                trip_id=trip.trip_id,
                state=trip.state.value,
                rider_id=trip.rider_id,
                driver_id=trip.driver_id,
                counterpart_name=counterpart_name,
                pickup_location=trip.pickup_location,
                dropoff_location=trip.dropoff_location,
                surge_multiplier=trip.surge_multiplier,
                fare=trip.fare,
            )

    state = rider.get_state(zone_loader)
    dna = rider.dna
    stats = rider.statistics

    # Compute next action for autonomous agents
    next_action_info = compute_next_action_response(rider, engine)
    action_history = compute_action_history_response(rider, engine)

    return RiderStateResponse(
        rider_id=rider.rider_id,
        status=state["status"],
        location=state["location"],
        current_rating=state["current_rating"],
        rating_count=state["rating_count"],
        active_trip=active_trip_info,
        next_action=next_action_info,
        action_history=action_history,
        zone_id=state["zone_id"],
        is_ephemeral=state["is_ephemeral"],
        is_puppet=state["is_puppet"],
        dna=RiderDNAResponse(
            behavior_factor=dna.behavior_factor,
            patience_threshold=dna.patience_threshold,
            max_surge_multiplier=dna.max_surge_multiplier,
            avg_rides_per_week=dna.avg_rides_per_week,
            frequent_destinations=dna.frequent_destinations,
            home_location=dna.home_location,
            first_name=dna.first_name,
            last_name=dna.last_name,
            email=dna.email,
            phone=dna.phone,
            payment_method_type=dna.payment_method_type,
            payment_method_masked=dna.payment_method_masked,
        ),
        statistics=RiderStatisticsResponse(
            trips_completed=stats.trips_completed,
            trips_cancelled=stats.trips_cancelled,
            trips_requested=stats.trips_requested,
            cancellation_rate=stats.cancellation_rate,
            requests_timed_out=stats.requests_timed_out,
            total_spent=stats.total_spent,
            avg_fare=stats.avg_fare,
            avg_wait_time_seconds=stats.avg_wait_time_seconds,
            avg_pickup_wait_seconds=stats.avg_pickup_wait_seconds,
            avg_rating_given=stats.avg_rating_given,
            surge_trips_percentage=stats.surge_trips_percentage,
        ),
    )


# --- Agent Control ---


@router.put("/drivers/{driver_id}/status", response_model=DriverStatusToggleResponse)
@limiter.limit("30/minute")
def toggle_driver_status(
    request: Request,
    driver_id: str,
    body: DriverStatusToggleRequest,
    engine: SimulationEngineDep,
) -> DriverStatusToggleResponse:
    """Toggle driver online/offline status.

    Can only toggle when driver has no active trip.
    """
    driver = engine._active_drivers.get(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail=f"Driver {driver_id} not found")

    if driver.active_trip:
        raise HTTPException(
            status_code=400,
            detail="Cannot toggle status while driver has active trip",
        )

    previous_status = driver.status

    if body.go_online:
        if driver.status == "available":
            raise HTTPException(status_code=400, detail="Driver is already available")
        driver.go_online()
    else:
        if driver.status == "offline":
            raise HTTPException(status_code=400, detail="Driver is already offline")
        driver.go_offline()

    return DriverStatusToggleResponse(
        driver_id=driver_id,
        previous_status=previous_status,
        new_status=driver.status,
    )


@router.post("/riders/{rider_id}/request-trip", response_model=RiderTripRequestResponse)
@limiter.limit("30/minute")
async def request_rider_trip(
    request: Request,
    rider_id: str,
    body: RiderTripRequestBody,
    engine: SimulationEngineDep,
    zone_loader: ZoneLoaderDep,
    matching_server: MatchingServerDep,
) -> RiderTripRequestResponse:
    """Request a trip for a rider with specified destination.

    The rider must be in 'offline' status to request a trip.
    """
    import uuid

    rider = engine._active_riders.get(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail=f"Rider {rider_id} not found")

    if rider.status != "idle":
        raise HTTPException(
            status_code=400,
            detail=f"Rider must be idle to request trip. Current status: {rider.status}",
        )

    if not rider.location:
        raise HTTPException(status_code=400, detail="Rider location not available")

    trip_id = str(uuid.uuid4())

    # Determine zones
    pickup_zone_id = (
        zone_loader.find_zone_for_location(rider.location[0], rider.location[1]) or "unknown"
    )
    dropoff_zone_id = (
        zone_loader.find_zone_for_location(body.destination[0], body.destination[1]) or "unknown"
    )

    # Get surge for pickup zone
    surge_multiplier = 1.0
    if matching_server._surge_calculator:
        surge_multiplier = matching_server._surge_calculator.get_surge(pickup_zone_id)

    # Calculate fare estimate (basic calculation)
    # Using a simple distance-based fare estimation
    from agents.dna import haversine_distance

    distance_km = haversine_distance(
        rider.location[0],
        rider.location[1],
        body.destination[0],
        body.destination[1],
    )
    base_fare = 5.0  # Base fare in BRL
    per_km_rate = 2.5  # Rate per km in BRL
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

    return RiderTripRequestResponse(
        rider_id=rider_id,
        trip_id=trip_id,
        pickup_location=rider.location,
        destination=body.destination,
        surge_multiplier=surge_multiplier,
        estimated_fare=round(fare, 2),
    )
