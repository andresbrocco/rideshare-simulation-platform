"""Trip event factory functions for integration tests."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional


# São Paulo coordinates (centro histórico)
DEFAULT_PICKUP_LOCATION = [-23.5505, -46.6333]
DEFAULT_DROPOFF_LOCATION = [-23.5629, -46.6544]
DEFAULT_ZONE_ID = "SP-001"


def generate_trip_event(
    event_type: str,
    trip_id: str,
    rider_id: str,
    timestamp: Optional[datetime] = None,
    driver_id: Optional[str] = None,
    pickup_location: Optional[List[float]] = None,
    dropoff_location: Optional[List[float]] = None,
    pickup_zone_id: str = DEFAULT_ZONE_ID,
    dropoff_zone_id: str = DEFAULT_ZONE_ID,
    surge_multiplier: float = 1.0,
    fare: float = 15.00,
    correlation_id: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Generate a single trip event.

    Args:
        event_type: Trip event type (e.g., 'trip.requested')
        trip_id: Unique trip identifier
        rider_id: Unique rider identifier
        timestamp: Event timestamp (defaults to now)
        driver_id: Driver identifier (null for requested events)
        pickup_location: [lat, lon] coordinates
        dropoff_location: [lat, lon] coordinates
        pickup_zone_id: Pickup zone identifier
        dropoff_zone_id: Dropoff zone identifier
        surge_multiplier: Surge pricing multiplier
        fare: Trip fare amount
        correlation_id: Correlation ID (defaults to trip_id)
        **kwargs: Additional event fields

    Returns:
        Trip event dictionary matching trip_event.json schema
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    if pickup_location is None:
        pickup_location = DEFAULT_PICKUP_LOCATION

    if dropoff_location is None:
        dropoff_location = DEFAULT_DROPOFF_LOCATION

    if correlation_id is None:
        correlation_id = trip_id

    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "timestamp": timestamp.isoformat(),
        "trip_id": trip_id,
        "rider_id": rider_id,
        "driver_id": driver_id,
        "pickup_location": pickup_location,
        "dropoff_location": dropoff_location,
        "pickup_zone_id": pickup_zone_id,
        "dropoff_zone_id": dropoff_zone_id,
        "surge_multiplier": surge_multiplier,
        "fare": fare,
        "correlation_id": correlation_id,
        "session_id": None,
        "causation_id": None,
        "route": None,
        "pickup_route": None,
        "route_progress_index": None,
        "pickup_route_progress_index": None,
        "offer_sequence": None,
        "cancelled_by": None,
        "cancellation_reason": None,
        "cancellation_stage": None,
    }

    # Merge additional kwargs
    event.update(kwargs)

    return event


def generate_trip_lifecycle(
    trip_id: Optional[str] = None,
    rider_id: Optional[str] = None,
    driver_id: Optional[str] = None,
    start_timestamp: Optional[datetime] = None,
    pickup_location: Optional[List[float]] = None,
    dropoff_location: Optional[List[float]] = None,
    pickup_zone_id: str = DEFAULT_ZONE_ID,
    dropoff_zone_id: str = DEFAULT_ZONE_ID,
    surge_multiplier: float = 1.0,
    fare: float = 15.00,
) -> List[Dict[str, Any]]:
    """Generate a complete trip lifecycle (happy path).

    Lifecycle states:
    1. trip.requested (rider requests trip)
    2. trip.matched (driver assigned)
    3. trip.driver_en_route (driver heading to pickup)
    4. trip.driver_arrived (driver at pickup location)
    5. trip.started (rider in vehicle)
    6. trip.completed (trip finished)

    Args:
        trip_id: Trip identifier (auto-generated if None)
        rider_id: Rider identifier (auto-generated if None)
        driver_id: Driver identifier (auto-generated if None)
        start_timestamp: Starting timestamp (defaults to now)
        pickup_location: [lat, lon] for pickup
        dropoff_location: [lat, lon] for dropoff
        pickup_zone_id: Pickup zone ID
        dropoff_zone_id: Dropoff zone ID
        surge_multiplier: Surge pricing multiplier
        fare: Trip fare

    Returns:
        List of 6 trip events in chronological order
    """
    if trip_id is None:
        trip_id = f"trip-{uuid.uuid4()}"

    if rider_id is None:
        rider_id = f"rider-{uuid.uuid4()}"

    if driver_id is None:
        driver_id = f"driver-{uuid.uuid4()}"

    if start_timestamp is None:
        start_timestamp = datetime.now(timezone.utc)

    # Time deltas between state transitions (simulated realistic intervals)
    time_deltas = {
        "requested_to_matched": timedelta(seconds=5),
        "matched_to_en_route": timedelta(seconds=2),
        "en_route_to_arrived": timedelta(minutes=3),
        "arrived_to_started": timedelta(seconds=30),
        "started_to_completed": timedelta(minutes=10),
    }

    events = []
    current_time = start_timestamp

    # 1. trip.requested
    events.append(
        generate_trip_event(
            event_type="trip.requested",
            trip_id=trip_id,
            rider_id=rider_id,
            timestamp=current_time,
            driver_id=None,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_zone_id=pickup_zone_id,
            dropoff_zone_id=dropoff_zone_id,
            surge_multiplier=surge_multiplier,
            fare=fare,
        )
    )
    current_time += time_deltas["requested_to_matched"]

    # 2. trip.matched
    events.append(
        generate_trip_event(
            event_type="trip.matched",
            trip_id=trip_id,
            rider_id=rider_id,
            timestamp=current_time,
            driver_id=driver_id,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_zone_id=pickup_zone_id,
            dropoff_zone_id=dropoff_zone_id,
            surge_multiplier=surge_multiplier,
            fare=fare,
        )
    )
    current_time += time_deltas["matched_to_en_route"]

    # 3. trip.driver_en_route
    events.append(
        generate_trip_event(
            event_type="trip.driver_en_route",
            trip_id=trip_id,
            rider_id=rider_id,
            timestamp=current_time,
            driver_id=driver_id,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_zone_id=pickup_zone_id,
            dropoff_zone_id=dropoff_zone_id,
            surge_multiplier=surge_multiplier,
            fare=fare,
        )
    )
    current_time += time_deltas["en_route_to_arrived"]

    # 4. trip.driver_arrived
    events.append(
        generate_trip_event(
            event_type="trip.driver_arrived",
            trip_id=trip_id,
            rider_id=rider_id,
            timestamp=current_time,
            driver_id=driver_id,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_zone_id=pickup_zone_id,
            dropoff_zone_id=dropoff_zone_id,
            surge_multiplier=surge_multiplier,
            fare=fare,
        )
    )
    current_time += time_deltas["arrived_to_started"]

    # 5. trip.started
    events.append(
        generate_trip_event(
            event_type="trip.started",
            trip_id=trip_id,
            rider_id=rider_id,
            timestamp=current_time,
            driver_id=driver_id,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_zone_id=pickup_zone_id,
            dropoff_zone_id=dropoff_zone_id,
            surge_multiplier=surge_multiplier,
            fare=fare,
        )
    )
    current_time += time_deltas["started_to_completed"]

    # 6. trip.completed
    events.append(
        generate_trip_event(
            event_type="trip.completed",
            trip_id=trip_id,
            rider_id=rider_id,
            timestamp=current_time,
            driver_id=driver_id,
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_zone_id=pickup_zone_id,
            dropoff_zone_id=dropoff_zone_id,
            surge_multiplier=surge_multiplier,
            fare=fare,
        )
    )

    return events
