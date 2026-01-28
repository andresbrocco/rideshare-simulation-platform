"""Sample event data generators for testing Bronze streaming jobs.

This module provides factory functions that generate realistic sample events
for testing all eight streaming jobs in the Bronze layer ingestion pipeline.
"""

import uuid
from datetime import datetime, timezone
from typing import Callable


def sample_trip_requested_event(
    trip_id: str | None = None,
    rider_id: str | None = None,
    session_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> dict:
    """Generate a sample trip.requested event.

    Args:
        trip_id: Optional trip ID (generated if not provided).
        rider_id: Optional rider ID (generated if not provided).
        session_id: Optional session ID for tracing.
        correlation_id: Optional correlation ID for tracing.
        causation_id: Optional causation ID for tracing.

    Returns:
        Dictionary representing a trip.requested event.
    """
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "trip.requested",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trip_id": trip_id or str(uuid.uuid4()),
        "rider_id": rider_id or str(uuid.uuid4()),
        "driver_id": None,
        "pickup_location": [-23.5505, -46.6333],
        "dropoff_location": [-23.5629, -46.6544],
        "pickup_zone_id": "zona-sul",
        "dropoff_zone_id": "centro",
        "surge_multiplier": 1.0,
        "fare": 0.0,
        "route": None,
        "session_id": session_id,
        "correlation_id": correlation_id,
        "causation_id": causation_id,
    }


def sample_trip_matched_event(
    trip_id: str | None = None,
    rider_id: str | None = None,
    driver_id: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Generate a sample trip.matched event.

    Args:
        trip_id: Optional trip ID (generated if not provided).
        rider_id: Optional rider ID (generated if not provided).
        driver_id: Optional driver ID (generated if not provided).
        session_id: Optional session ID for tracing.

    Returns:
        Dictionary representing a trip.matched event.
    """
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "trip.matched",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trip_id": trip_id or str(uuid.uuid4()),
        "rider_id": rider_id or str(uuid.uuid4()),
        "driver_id": driver_id or str(uuid.uuid4()),
        "pickup_location": [-23.5505, -46.6333],
        "dropoff_location": [-23.5629, -46.6544],
        "pickup_zone_id": "zona-sul",
        "dropoff_zone_id": "centro",
        "surge_multiplier": 1.2,
        "fare": 0.0,
        "route": None,
        "session_id": session_id,
        "correlation_id": trip_id,
        "causation_id": None,
    }


def sample_trip_completed_event(
    trip_id: str | None = None,
    rider_id: str | None = None,
    driver_id: str | None = None,
    fare: float = 25.50,
) -> dict:
    """Generate a sample trip.completed event.

    Args:
        trip_id: Optional trip ID (generated if not provided).
        rider_id: Optional rider ID (generated if not provided).
        driver_id: Optional driver ID (generated if not provided).
        fare: Trip fare amount (default 25.50).

    Returns:
        Dictionary representing a trip.completed event.
    """
    route = [
        [-23.5505, -46.6333],
        [-23.5520, -46.6350],
        [-23.5540, -46.6370],
        [-23.5629, -46.6544],
    ]

    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "trip.completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trip_id": trip_id or str(uuid.uuid4()),
        "rider_id": rider_id or str(uuid.uuid4()),
        "driver_id": driver_id or str(uuid.uuid4()),
        "pickup_location": [-23.5505, -46.6333],
        "dropoff_location": [-23.5629, -46.6544],
        "pickup_zone_id": "zona-sul",
        "dropoff_zone_id": "centro",
        "surge_multiplier": 1.2,
        "fare": fare,
        "route": route,
        "session_id": None,
        "correlation_id": trip_id,
        "causation_id": None,
    }


def sample_gps_ping_event(
    entity_type: str = "driver",
    entity_id: str | None = None,
    trip_id: str | None = None,
    trip_state: str | None = None,
    heading: float | None = 90.0,
    speed: float | None = 45.0,
) -> dict:
    """Generate a sample GPS ping event.

    Args:
        entity_type: Either "driver" or "rider".
        entity_id: Optional entity ID (generated if not provided).
        trip_id: Optional trip ID if entity is on a trip.
        trip_state: Optional trip state (e.g., "STARTED", "DRIVER_EN_ROUTE").
        heading: Optional heading in degrees (default 90.0).
        speed: Optional speed in km/h (default 45.0).

    Returns:
        Dictionary representing a GPS ping event.
    """
    return {
        "event_id": str(uuid.uuid4()),
        "entity_type": entity_type,
        "entity_id": entity_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": [-23.5505 + (uuid.uuid4().int % 100) * 0.0001, -46.6333],
        "heading": heading,
        "speed": speed,
        "accuracy": 5.0,
        "trip_id": trip_id,
        "trip_state": trip_state,
        "route_progress_index": 10 if trip_state else None,
        "pickup_route_progress_index": 5 if trip_state == "DRIVER_EN_ROUTE" else None,
        "session_id": None,
        "correlation_id": trip_id,
        "causation_id": None,
    }


def sample_driver_status_event(
    driver_id: str | None = None,
    new_status: str = "online",
    previous_status: str = "offline",
    trigger: str = "app_open",
) -> dict:
    """Generate a sample driver status change event.

    Args:
        driver_id: Optional driver ID (generated if not provided).
        new_status: New driver status (default "online").
        previous_status: Previous driver status (default "offline").
        trigger: What triggered the status change (default "app_open").

    Returns:
        Dictionary representing a driver status event.
    """
    return {
        "event_id": str(uuid.uuid4()),
        "driver_id": driver_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "new_status": new_status,
        "previous_status": previous_status,
        "trigger": trigger,
        "location": [-23.5505, -46.6333],
        "session_id": None,
        "correlation_id": None,
        "causation_id": None,
    }


def sample_surge_update_event(
    zone_id: str = "zona-sul",
    previous_multiplier: float = 1.0,
    new_multiplier: float = 1.5,
) -> dict:
    """Generate a sample surge pricing update event.

    Args:
        zone_id: Zone ID for the surge update.
        previous_multiplier: Previous surge multiplier (default 1.0).
        new_multiplier: New surge multiplier (default 1.5).

    Returns:
        Dictionary representing a surge update event.
    """
    return {
        "event_id": str(uuid.uuid4()),
        "zone_id": zone_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "previous_multiplier": previous_multiplier,
        "new_multiplier": new_multiplier,
        "available_drivers": 5,
        "pending_requests": 15,
        "calculation_window_seconds": 60,
        "session_id": None,
        "correlation_id": None,
        "causation_id": None,
    }


def sample_rating_event(
    trip_id: str | None = None,
    rider_id: str | None = None,
    driver_id: str | None = None,
    rating: int = 5,
) -> dict:
    """Generate a sample rating event.

    Args:
        trip_id: Optional trip ID (generated if not provided).
        rider_id: Optional rider ID (generated if not provided).
        driver_id: Optional driver ID (generated if not provided).
        rating: Rating value 1-5 (default 5).

    Returns:
        Dictionary representing a rating event.
    """
    return {
        "event_id": str(uuid.uuid4()),
        "trip_id": trip_id or str(uuid.uuid4()),
        "rider_id": rider_id or str(uuid.uuid4()),
        "driver_id": driver_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rating": rating,
        "comment": "Great ride!" if rating >= 4 else "Could be better",
        "session_id": None,
        "correlation_id": trip_id,
        "causation_id": None,
    }


def sample_payment_event(
    trip_id: str | None = None,
    rider_id: str | None = None,
    driver_id: str | None = None,
    amount: float = 25.50,
    status: str = "completed",
) -> dict:
    """Generate a sample payment event.

    Args:
        trip_id: Optional trip ID (generated if not provided).
        rider_id: Optional rider ID (generated if not provided).
        driver_id: Optional driver ID (generated if not provided).
        amount: Payment amount (default 25.50).
        status: Payment status (default "completed").

    Returns:
        Dictionary representing a payment event.
    """
    return {
        "event_id": str(uuid.uuid4()),
        "trip_id": trip_id or str(uuid.uuid4()),
        "rider_id": rider_id or str(uuid.uuid4()),
        "driver_id": driver_id or str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "amount": amount,
        "currency": "BRL",
        "payment_method": "credit_card",
        "status": status,
        "transaction_id": str(uuid.uuid4()),
        "session_id": None,
        "correlation_id": trip_id,
        "causation_id": None,
    }


def sample_driver_profile_event(driver_id: str | None = None) -> dict:
    """Generate a sample driver profile event.

    Args:
        driver_id: Optional driver ID (generated if not provided).

    Returns:
        Dictionary representing a driver profile event.
    """
    driver_id = driver_id or str(uuid.uuid4())
    return {
        "event_id": str(uuid.uuid4()),
        "driver_id": driver_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name": "Jose Silva",
        "email": f"jose.{driver_id[:8]}@email.com",
        "phone": "+5511999990000",
        "vehicle_type": "sedan",
        "vehicle_make": "Toyota",
        "vehicle_model": "Corolla",
        "vehicle_year": 2022,
        "license_plate": "ABC1234",
        "rating": 4.8,
        "total_trips": 150,
        "session_id": None,
        "correlation_id": None,
        "causation_id": None,
    }


def sample_rider_profile_event(rider_id: str | None = None) -> dict:
    """Generate a sample rider profile event.

    Args:
        rider_id: Optional rider ID (generated if not provided).

    Returns:
        Dictionary representing a rider profile event.
    """
    rider_id = rider_id or str(uuid.uuid4())
    return {
        "event_id": str(uuid.uuid4()),
        "rider_id": rider_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "name": "Maria Santos",
        "email": f"maria.{rider_id[:8]}@email.com",
        "phone": "+5511888880000",
        "preferred_payment_method": "credit_card",
        "rating": 4.9,
        "total_trips": 75,
        "session_id": None,
        "correlation_id": None,
        "causation_id": None,
    }


def sample_malformed_trip_event() -> dict:
    """Generate a malformed trip event missing required fields.

    Returns:
        Dictionary representing an incomplete trip event.
    """
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "trip.requested",
        # Missing: trip_id, rider_id, pickup_location, dropoff_location, etc.
    }


def sample_malformed_gps_event() -> dict:
    """Generate a malformed GPS event missing the location field.

    Returns:
        Dictionary representing an incomplete GPS event.
    """
    return {
        "event_id": str(uuid.uuid4()),
        "entity_type": "driver",
        "entity_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        # Missing: location field
        "heading": 90.0,
        "speed": 45.0,
    }


def generate_event_batch(
    event_generator: Callable,
    count: int = 100,
    **kwargs,
) -> list[dict]:
    """Generate a batch of events using the specified generator.

    Args:
        event_generator: Function that generates a single event.
        count: Number of events to generate (default 100).
        **kwargs: Additional arguments passed to the generator.

    Returns:
        List of generated event dictionaries.
    """
    return [event_generator(**kwargs) for _ in range(count)]
