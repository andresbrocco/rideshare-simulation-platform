"""Rider event factory functions for integration tests."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
import random


# São Paulo default location (centro histórico)
DEFAULT_LOCATION = [-23.5505, -46.6333]


def generate_rider_profile_event(
    event_type: str,
    rider_id: str,
    timestamp: Optional[datetime] = None,
    first_name: str = "Maria",
    last_name: str = "Santos",
    email: Optional[str] = None,
    phone: str = "+55 11 98765-4321",
    home_location: Optional[List[float]] = None,
    payment_method_type: str = "credit_card",
    payment_method_masked: str = "****1234",
    behavior_factor: Optional[float] = None,
    correlation_id: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Generate a rider profile event.

    Args:
        event_type: Event type ('rider.created' or 'rider.updated')
        rider_id: Unique rider identifier
        timestamp: Event timestamp (defaults to now)
        first_name: Rider's first name
        last_name: Rider's last name
        email: Rider's email (auto-generated if None)
        phone: Rider's phone number
        home_location: Home location [lat, lon] (defaults to São Paulo centro)
        payment_method_type: Payment method type ('credit_card' or 'digital_wallet')
        payment_method_masked: Masked payment method identifier
        behavior_factor: Behavioral factor (0-1, only in rider.created events)
        correlation_id: Correlation ID (optional)
        **kwargs: Additional event fields

    Returns:
        Rider profile event dictionary matching rider_profile_event.json schema
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    if email is None:
        email = f"{first_name.lower()}.{last_name.lower()}@example.com"

    if home_location is None:
        home_location = DEFAULT_LOCATION.copy()

    # behavior_factor only in rider.created events
    if event_type == "rider.created" and behavior_factor is None:
        behavior_factor = random.uniform(0.5, 1.0)
    elif event_type == "rider.updated":
        behavior_factor = None

    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "rider_id": rider_id,
        "timestamp": timestamp.isoformat(),
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "home_location": home_location,
        "payment_method_type": payment_method_type,
        "payment_method_masked": payment_method_masked,
        "behavior_factor": behavior_factor,
        "session_id": None,
        "correlation_id": correlation_id,
        "causation_id": None,
    }

    # Merge additional kwargs
    event.update(kwargs)

    return event


def generate_rider_profile_with_update(
    rider_id: str,
    create_timestamp: Optional[datetime] = None,
    update_timestamp: Optional[datetime] = None,
    update_fields: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Generate rider.created and rider.updated events for SCD Type 2 testing.

    Args:
        rider_id: Unique rider identifier
        create_timestamp: Creation timestamp (defaults to now)
        update_timestamp: Update timestamp (defaults to create + 1 hour)
        update_fields: Fields to change in update event (e.g., {'payment_method_masked': '****5678'})

    Returns:
        List containing [rider.created event, rider.updated event]
    """
    if create_timestamp is None:
        create_timestamp = datetime.now(timezone.utc)

    if update_timestamp is None:
        update_timestamp = create_timestamp + timedelta(hours=1)

    if update_fields is None:
        update_fields = {
            "payment_method_type": "digital_wallet",
            "payment_method_masked": "****5678",
        }

    # Create event
    create_event = generate_rider_profile_event(
        event_type="rider.created",
        rider_id=rider_id,
        timestamp=create_timestamp,
    )

    # Update event with modified fields
    update_event_data = create_event.copy()
    update_event_data["event_id"] = str(uuid.uuid4())
    update_event_data["event_type"] = "rider.updated"
    update_event_data["timestamp"] = update_timestamp.isoformat()
    update_event_data["behavior_factor"] = None  # Not in update events
    update_event_data.update(update_fields)

    return [create_event, update_event_data]


def generate_multiple_rider_profiles(
    num_riders: int,
    start_timestamp: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Generate rider.created events for multiple riders.

    Args:
        num_riders: Number of riders to generate
        start_timestamp: Starting timestamp (defaults to now)

    Returns:
        List of rider.created events
    """
    if start_timestamp is None:
        start_timestamp = datetime.now(timezone.utc)

    first_names = ["Maria", "Ana", "Carlos", "João", "Paula", "Pedro", "Julia", "Lucas"]
    last_names = [
        "Silva",
        "Santos",
        "Oliveira",
        "Souza",
        "Lima",
        "Ferreira",
        "Costa",
        "Alves",
    ]
    payment_types = ["credit_card", "digital_wallet"]

    events = []

    for i in range(num_riders):
        rider_id = f"rider-{uuid.uuid4()}"
        first_name = random.choice(first_names)
        last_name = random.choice(last_names)
        payment_type = random.choice(payment_types)

        event = generate_rider_profile_event(
            event_type="rider.created",
            rider_id=rider_id,
            timestamp=start_timestamp + timedelta(seconds=i),
            first_name=first_name,
            last_name=last_name,
            payment_method_type=payment_type,
            payment_method_masked=f"****{random.randint(1000, 9999)}",
        )
        events.append(event)

    return events


def generate_rider_profile_events(
    rider_ids: List[str],
    start_timestamp: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Generate rider.created events for specified riders.

    Convenience wrapper for conftest fixtures.

    Args:
        rider_ids: List of rider identifiers
        start_timestamp: Starting timestamp (defaults to now)

    Returns:
        List of rider.created events
    """
    if start_timestamp is None:
        start_timestamp = datetime.now(timezone.utc)

    events = []
    for i, rider_id in enumerate(rider_ids):
        event = generate_rider_profile_event(
            event_type="rider.created",
            rider_id=rider_id,
            timestamp=start_timestamp + timedelta(seconds=i),
        )
        events.append(event)

    return events
