"""GPS ping event factory functions for integration tests."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
import random


# São Paulo bounding box (approximate)
SAO_PAULO_LAT_MIN = -23.75
SAO_PAULO_LAT_MAX = -23.35
SAO_PAULO_LON_MIN = -46.82
SAO_PAULO_LON_MAX = -46.36

# Default location (centro histórico)
DEFAULT_LOCATION = [-23.5505, -46.6333]


def generate_gps_ping(
    entity_type: str,
    entity_id: str,
    timestamp: Optional[datetime] = None,
    location: Optional[List[float]] = None,
    heading: Optional[float] = None,
    speed: Optional[float] = None,
    accuracy: float = 10.0,
    trip_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Generate a single GPS ping event.

    Args:
        entity_type: Entity type ('driver' or 'rider')
        entity_id: Unique entity identifier
        timestamp: Event timestamp (defaults to now)
        location: [lat, lon] coordinates (defaults to São Paulo centro)
        heading: Heading in degrees (0-359), optional
        speed: Speed in km/h, optional
        accuracy: GPS accuracy in meters (default 10.0)
        trip_id: Associated trip ID (optional)
        correlation_id: Correlation ID (defaults to trip_id if present)
        **kwargs: Additional event fields

    Returns:
        GPS ping event dictionary matching gps_ping_event.json schema
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    if location is None:
        location = DEFAULT_LOCATION.copy()

    if correlation_id is None and trip_id is not None:
        correlation_id = trip_id

    event = {
        "event_id": str(uuid.uuid4()),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "timestamp": timestamp.isoformat(),
        "location": location,
        "heading": heading,
        "speed": speed,
        "accuracy": accuracy,
        "trip_id": trip_id,
        "session_id": None,
        "correlation_id": correlation_id,
        "causation_id": None,
        "trip_state": None,
        "route_progress_index": None,
        "pickup_route_progress_index": None,
    }

    # Merge additional kwargs
    event.update(kwargs)

    return event


def generate_random_sao_paulo_location() -> List[float]:
    """Generate random coordinates within São Paulo bounds.

    Returns:
        [lat, lon] within São Paulo bounding box
    """
    lat = random.uniform(SAO_PAULO_LAT_MIN, SAO_PAULO_LAT_MAX)
    lon = random.uniform(SAO_PAULO_LON_MIN, SAO_PAULO_LON_MAX)
    return [lat, lon]


def generate_gps_ping_sequence(
    entity_type: str,
    entity_id: str,
    num_pings: int,
    start_timestamp: Optional[datetime] = None,
    start_location: Optional[List[float]] = None,
    ping_interval: timedelta = timedelta(seconds=5),
    add_movement: bool = True,
    trip_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Generate a sequence of GPS pings for a single entity.

    Args:
        entity_type: Entity type ('driver' or 'rider')
        entity_id: Unique entity identifier
        num_pings: Number of pings to generate
        start_timestamp: Starting timestamp (defaults to now)
        start_location: Starting location (defaults to random São Paulo)
        ping_interval: Time between pings (default 5 seconds)
        add_movement: If True, simulate movement with changing coordinates
        trip_id: Optional trip ID for correlation

    Returns:
        List of GPS ping events in chronological order
    """
    if start_timestamp is None:
        start_timestamp = datetime.now(timezone.utc)

    if start_location is None:
        start_location = generate_random_sao_paulo_location()

    events = []
    current_time = start_timestamp
    current_location = start_location.copy()
    current_heading = random.uniform(0, 359)
    current_speed = random.uniform(20, 50)  # km/h

    for i in range(num_pings):
        # Simulate movement
        if add_movement and i > 0:
            # Small random changes to simulate realistic GPS drift and movement
            lat_delta = random.uniform(-0.001, 0.001)
            lon_delta = random.uniform(-0.001, 0.001)
            current_location[0] += lat_delta
            current_location[1] += lon_delta

            # Ensure within São Paulo bounds
            current_location[0] = max(
                SAO_PAULO_LAT_MIN, min(SAO_PAULO_LAT_MAX, current_location[0])
            )
            current_location[1] = max(
                SAO_PAULO_LON_MIN, min(SAO_PAULO_LON_MAX, current_location[1])
            )

            # Update heading and speed slightly
            current_heading = (current_heading + random.uniform(-10, 10)) % 360
            current_speed = max(0, current_speed + random.uniform(-5, 5))

        event = generate_gps_ping(
            entity_type=entity_type,
            entity_id=entity_id,
            timestamp=current_time,
            location=current_location.copy(),
            heading=current_heading,
            speed=current_speed,
            accuracy=random.uniform(5.0, 15.0),
            trip_id=trip_id,
        )

        events.append(event)
        current_time += ping_interval

    return events


def generate_gps_pings(
    driver_id: str,
    num_pings: int = 20,
    start_location: Optional[List[float]] = None,
    start_timestamp: Optional[datetime] = None,
    ping_interval: timedelta = timedelta(seconds=5),
) -> List[Dict[str, Any]]:
    """Generate GPS pings for a single driver.

    Convenience wrapper around generate_gps_ping_sequence for conftest fixtures.

    Args:
        driver_id: Unique driver identifier
        num_pings: Number of pings to generate (default 20)
        start_location: Starting location [lat, lon] (defaults to São Paulo centro)
        start_timestamp: Starting timestamp (defaults to now)
        ping_interval: Time between pings (default 5 seconds)

    Returns:
        List of GPS ping events in chronological order
    """
    if start_location is None:
        start_location = DEFAULT_LOCATION.copy()

    return generate_gps_ping_sequence(
        entity_type="driver",
        entity_id=driver_id,
        num_pings=num_pings,
        start_timestamp=start_timestamp,
        start_location=start_location,
        ping_interval=ping_interval,
        add_movement=True,
    )


def generate_multi_driver_gps_pings(
    num_drivers: int,
    pings_per_driver: int,
    start_timestamp: Optional[datetime] = None,
    ping_interval: timedelta = timedelta(seconds=5),
) -> List[Dict[str, Any]]:
    """Generate GPS pings for multiple drivers.

    Useful for high-volume ingestion tests (FJ-002).

    Args:
        num_drivers: Number of drivers to generate pings for
        pings_per_driver: Number of pings per driver
        start_timestamp: Starting timestamp (defaults to now)
        ping_interval: Time between pings (default 5 seconds)

    Returns:
        List of all GPS ping events (num_drivers * pings_per_driver)
    """
    if start_timestamp is None:
        start_timestamp = datetime.now(timezone.utc)

    all_events = []

    for driver_idx in range(num_drivers):
        driver_id = f"driver-{uuid.uuid4()}"
        driver_pings = generate_gps_ping_sequence(
            entity_type="driver",
            entity_id=driver_id,
            num_pings=pings_per_driver,
            start_timestamp=start_timestamp,
            start_location=generate_random_sao_paulo_location(),
            ping_interval=ping_interval,
            add_movement=True,
        )
        all_events.extend(driver_pings)

    return all_events
