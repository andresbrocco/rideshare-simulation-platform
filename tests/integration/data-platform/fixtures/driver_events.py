"""Driver event factory functions for integration tests."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional


# São Paulo default location (centro histórico)
DEFAULT_LOCATION = [-23.5505, -46.6333]


def generate_driver_status_event(
    driver_id: str,
    new_status: str,
    trigger: str,
    timestamp: Optional[datetime] = None,
    previous_status: Optional[str] = None,
    location: Optional[List[float]] = None,
    correlation_id: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Generate a driver status change event.

    Args:
        driver_id: Unique driver identifier
        new_status: New driver status ('online', 'offline', 'en_route_pickup', 'en_route_destination')
        trigger: What triggered the status change
        timestamp: Event timestamp (defaults to now)
        previous_status: Previous driver status (optional)
        location: Driver's current location [lat, lon] (defaults to São Paulo centro)
        correlation_id: Correlation ID (optional)
        **kwargs: Additional event fields

    Returns:
        Driver status event dictionary matching driver_status_event.json schema
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    if location is None:
        location = DEFAULT_LOCATION.copy()

    event = {
        "event_id": str(uuid.uuid4()),
        "driver_id": driver_id,
        "timestamp": timestamp.isoformat(),
        "previous_status": previous_status,
        "new_status": new_status,
        "trigger": trigger,
        "location": location,
        "session_id": None,
        "correlation_id": correlation_id,
        "causation_id": None,
    }

    # Merge additional kwargs
    event.update(kwargs)

    return event


def generate_driver_status_transitions(
    driver_id: str,
    transitions: List[tuple],
    start_timestamp: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Generate a sequence of driver status transitions.

    Args:
        driver_id: Unique driver identifier
        transitions: List of (new_status, trigger) tuples
        start_timestamp: Starting timestamp (defaults to now)

    Returns:
        List of driver status events in chronological order

    Example:
        transitions = [
            ('online', 'driver_app_opened'),
            ('en_route_pickup', 'trip_matched'),
            ('en_route_destination', 'trip_started'),
            ('online', 'trip_completed'),
            ('offline', 'driver_app_closed'),
        ]
    """
    if start_timestamp is None:
        start_timestamp = datetime.now(timezone.utc)

    events = []
    previous_status = None

    for i, (new_status, trigger) in enumerate(transitions):
        timestamp = start_timestamp + timedelta(minutes=i * 5)
        event = generate_driver_status_event(
            driver_id=driver_id,
            new_status=new_status,
            trigger=trigger,
            timestamp=timestamp,
            previous_status=previous_status,
        )
        events.append(event)
        previous_status = new_status

    return events


def generate_driver_profile_event(
    event_type: str,
    driver_id: str,
    timestamp: Optional[datetime] = None,
    first_name: str = "João",
    last_name: str = "Silva",
    email: Optional[str] = None,
    phone: str = "+55 11 91234-5678",
    home_location: Optional[List[float]] = None,
    preferred_zones: Optional[List[str]] = None,
    shift_preference: str = "flexible",
    vehicle_make: str = "Toyota",
    vehicle_model: str = "Corolla",
    vehicle_year: int = 2020,
    license_plate: str = "ABC1D23",
    correlation_id: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Generate a driver profile event.

    Args:
        event_type: Event type ('driver.created' or 'driver.updated')
        driver_id: Unique driver identifier
        timestamp: Event timestamp (defaults to now)
        first_name: Driver's first name
        last_name: Driver's last name
        email: Driver's email (auto-generated if None)
        phone: Driver's phone number
        home_location: Home location [lat, lon] (defaults to São Paulo centro)
        preferred_zones: List of preferred zone IDs
        shift_preference: Shift preference ('morning', 'afternoon', 'evening', 'night', 'flexible')
        vehicle_make: Vehicle manufacturer
        vehicle_model: Vehicle model
        vehicle_year: Vehicle year of manufacture
        license_plate: Vehicle license plate
        correlation_id: Correlation ID (optional)
        **kwargs: Additional event fields

    Returns:
        Driver profile event dictionary matching driver_profile_event.json schema
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    if email is None:
        email = f"{first_name.lower()}.{last_name.lower()}@example.com"

    if home_location is None:
        home_location = DEFAULT_LOCATION.copy()

    if preferred_zones is None:
        preferred_zones = ["SP-001", "SP-002"]

    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "driver_id": driver_id,
        "timestamp": timestamp.isoformat(),
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "home_location": home_location,
        "preferred_zones": preferred_zones,
        "shift_preference": shift_preference,
        "vehicle_make": vehicle_make,
        "vehicle_model": vehicle_model,
        "vehicle_year": vehicle_year,
        "license_plate": license_plate,
        "session_id": None,
        "correlation_id": correlation_id,
        "causation_id": None,
    }

    # Merge additional kwargs
    event.update(kwargs)

    return event


def generate_driver_profile_with_update(
    driver_id: str,
    create_timestamp: Optional[datetime] = None,
    update_timestamp: Optional[datetime] = None,
    update_fields: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Generate driver.created and driver.updated events for SCD Type 2 testing.

    Args:
        driver_id: Unique driver identifier
        create_timestamp: Creation timestamp (defaults to now)
        update_timestamp: Update timestamp (defaults to create + 1 hour)
        update_fields: Fields to change in update event (e.g., {'vehicle_model': 'Civic'})

    Returns:
        List containing [driver.created event, driver.updated event]
    """
    if create_timestamp is None:
        create_timestamp = datetime.now(timezone.utc)

    if update_timestamp is None:
        update_timestamp = create_timestamp + timedelta(hours=1)

    if update_fields is None:
        update_fields = {"vehicle_model": "Civic", "license_plate": "XYZ9W87"}

    # Create event
    create_event = generate_driver_profile_event(
        event_type="driver.created",
        driver_id=driver_id,
        timestamp=create_timestamp,
    )

    # Update event with modified fields
    update_event_data = create_event.copy()
    update_event_data["event_id"] = str(uuid.uuid4())
    update_event_data["event_type"] = "driver.updated"
    update_event_data["timestamp"] = update_timestamp.isoformat()
    update_event_data.update(update_fields)

    return [create_event, update_event_data]


def generate_driver_status_events(
    driver_id: str,
    num_transitions: int = 5,
    start_timestamp: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Generate driver status events with typical transitions.

    Convenience wrapper for conftest fixtures.

    Args:
        driver_id: Unique driver identifier
        num_transitions: Number of status transitions (default 5)
        start_timestamp: Starting timestamp (defaults to now)

    Returns:
        List of driver status events in chronological order
    """
    # Define typical status transitions
    typical_transitions = [
        ("online", "driver_app_opened"),
        ("en_route_pickup", "trip_matched"),
        ("en_route_destination", "trip_started"),
        ("online", "trip_completed"),
        ("offline", "driver_app_closed"),
    ]

    # Use specified number of transitions (up to available)
    transitions = typical_transitions[:num_transitions]

    return generate_driver_status_transitions(
        driver_id=driver_id,
        transitions=transitions,
        start_timestamp=start_timestamp,
    )


def generate_driver_profile_events(
    driver_ids: List[str],
    start_timestamp: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Generate driver.created events for multiple drivers.

    Convenience wrapper for conftest fixtures.

    Args:
        driver_ids: List of driver identifiers
        start_timestamp: Starting timestamp (defaults to now)

    Returns:
        List of driver.created events
    """
    if start_timestamp is None:
        start_timestamp = datetime.now(timezone.utc)

    events = []
    for i, driver_id in enumerate(driver_ids):
        event = generate_driver_profile_event(
            event_type="driver.created",
            driver_id=driver_id,
            timestamp=start_timestamp + timedelta(seconds=i),
        )
        events.append(event)

    return events
