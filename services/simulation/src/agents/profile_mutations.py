"""Profile mutation logic for generating realistic profile updates.

This module provides functions to generate realistic profile mutations
for SCD Type 2 tracking in the data warehouse. Mutations represent
real-world changes like vehicle updates, contact info changes, etc.
"""

import random
from typing import Any

from agents.dna import DriverDNA, RiderDNA, ShiftPreference
from agents.faker_provider import create_faker_instance


def mutate_driver_profile(dna: DriverDNA) -> dict[str, Any]:
    """Generate mutated driver profile fields.

    Probabilities:
    - Vehicle change: 40% (make, model, year, license plate)
    - Phone change: 20%
    - Email change: 15%
    - Shift preference change: 25%

    Args:
        dna: The driver's current DNA (used for context, not modified)

    Returns:
        Dictionary of changed fields with new values.
        Empty dict if no changes (should not happen in normal flow).
    """
    fake = create_faker_instance()
    changes: dict[str, Any] = {}
    roll = random.random()

    if roll < 0.40:
        # Vehicle change - driver got a new car
        vehicle = fake.vehicle_br()
        changes["vehicle_make"] = vehicle["make"]
        changes["vehicle_model"] = vehicle["model"]
        changes["vehicle_year"] = vehicle["year"]
        changes["license_plate"] = fake.license_plate_br()
    elif roll < 0.60:
        # Phone number change
        changes["phone"] = fake.phone_br_mobile_sp()
    elif roll < 0.75:
        # Email change
        changes["email"] = fake.email()
    else:
        # Shift preference change - driver adjusting schedule
        current_shift = dna.shift_preference
        options = [s for s in ShiftPreference if s != current_shift]
        changes["shift_preference"] = random.choice(options).value

    return changes


def mutate_rider_profile(dna: RiderDNA) -> dict[str, Any]:
    """Generate mutated rider profile fields.

    Probabilities:
    - Payment method change: 50% (type and masked value)
    - Phone change: 25%
    - Email change: 25%

    Args:
        dna: The rider's current DNA (used for context, not modified)

    Returns:
        Dictionary of changed fields with new values.
        Empty dict if no changes (should not happen in normal flow).
    """
    fake = create_faker_instance()
    changes: dict[str, Any] = {}
    roll = random.random()

    if roll < 0.50:
        # Payment method change - added new card or wallet
        payment = fake.payment_method_br()
        changes["payment_method_type"] = payment["type"]
        changes["payment_method_masked"] = payment["masked"]
    elif roll < 0.75:
        # Phone number change
        changes["phone"] = fake.phone_br_mobile_sp()
    else:
        # Email change
        changes["email"] = fake.email()

    return changes
