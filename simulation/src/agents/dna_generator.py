"""DNA generators for creating synthetic driver and rider profiles."""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from agents.dna import DriverDNA, RiderDNA, ShiftPreference, haversine_distance
from agents.faker_provider import create_faker_instance

if TYPE_CHECKING:
    from faker.proxy import Faker

# Module-level faker instance for production (unseeded for variety)
_faker: Faker = create_faker_instance()

# Geographic bounds for Sao Paulo
SAO_PAULO_LAT_MIN = -24.0
SAO_PAULO_LAT_MAX = -23.0
SAO_PAULO_LON_MIN = -47.0
SAO_PAULO_LON_MAX = -46.0

# Time affinity patterns for rider destinations
TIME_AFFINITY_PATTERNS = [
    [7, 8, 9],  # Morning commute
    [17, 18, 19],  # Evening return
    [10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 22, 23],  # Leisure
]


def generate_driver_dna(faker: Faker | None = None) -> DriverDNA:
    """Generate random driver DNA with realistic Brazilian driver profile.

    Args:
        faker: Optional Faker instance. Uses module-level instance if not provided.
               Pass a seeded Faker for deterministic output.

    Returns:
        DriverDNA with randomly generated attributes.
    """
    fake = faker or _faker

    # Behavioral parameters (immutable)
    acceptance_rate = random.uniform(0.7, 0.95)
    cancellation_tendency = random.uniform(0.01, 0.1)

    # Service quality skewed toward higher values
    service_quality = max(0.6, min(1.0, random.gauss(0.85, 0.1)))

    # Response time with normal distribution
    response_time = max(3.0, min(12.0, random.gauss(6.0, 2.0)))

    min_rider_rating = random.uniform(3.0, 4.5)

    # Home location
    home_lat = random.uniform(SAO_PAULO_LAT_MIN, SAO_PAULO_LAT_MAX)
    home_lon = random.uniform(SAO_PAULO_LON_MIN, SAO_PAULO_LON_MAX)
    home_location = (home_lat, home_lon)

    # Preferred zones (placeholder for now)
    num_zones = random.randint(1, 3)
    preferred_zones = [f"zone_{i}" for i in range(num_zones)]

    # Shift preference with weighted distribution
    shift_weights = {
        ShiftPreference.MORNING: 0.15,
        ShiftPreference.AFTERNOON: 0.25,
        ShiftPreference.EVENING: 0.25,
        ShiftPreference.NIGHT: 0.15,
        ShiftPreference.FLEXIBLE: 0.20,
    }
    shift_preference = random.choices(
        list(shift_weights.keys()), weights=list(shift_weights.values()), k=1
    )[0]

    avg_hours_per_day = random.randint(4, 12)
    avg_days_per_week = random.randint(3, 7)

    # Vehicle info from Faker
    vehicle = fake.vehicle_br()
    vehicle_make = vehicle["make"]
    vehicle_model = vehicle["model"]
    vehicle_year = vehicle["year"]
    license_plate = fake.license_plate_br()

    # Personal info from Faker
    first_name = fake.first_name()
    last_name = fake.last_name()
    email = fake.email()
    phone = fake.phone_br_mobile_sp()

    return DriverDNA(
        acceptance_rate=acceptance_rate,
        cancellation_tendency=cancellation_tendency,
        service_quality=service_quality,
        response_time=response_time,
        min_rider_rating=min_rider_rating,
        home_location=home_location,
        preferred_zones=preferred_zones,
        shift_preference=shift_preference,
        avg_hours_per_day=avg_hours_per_day,
        avg_days_per_week=avg_days_per_week,
        vehicle_make=vehicle_make,
        vehicle_model=vehicle_model,
        vehicle_year=vehicle_year,
        license_plate=license_plate,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
    )


def _generate_destination_near(
    home_lat: float, home_lon: float, min_km: float = 0.8, max_km: float = 20.0
) -> tuple[float, float] | None:
    """Generate random coordinates within min_km-max_km of home, within Sao Paulo bounds."""
    # Generate random bearing and distance
    bearing = random.uniform(0, 2 * math.pi)
    distance = random.uniform(min_km, max_km)

    # Convert to lat/lon offset
    # 1 degree lat ≈ 111 km, 1 degree lon ≈ 111 * cos(lat) km
    delta_lat = (distance * math.cos(bearing)) / 111.0
    delta_lon = (distance * math.sin(bearing)) / (111.0 * math.cos(math.radians(home_lat)))

    new_lat = home_lat + delta_lat
    new_lon = home_lon + delta_lon

    # Check bounds
    if not (SAO_PAULO_LAT_MIN <= new_lat <= SAO_PAULO_LAT_MAX):
        return None
    if not (SAO_PAULO_LON_MIN <= new_lon <= SAO_PAULO_LON_MAX):
        return None

    # Verify actual distance is within limits
    actual_distance = haversine_distance(home_lat, home_lon, new_lat, new_lon)
    if actual_distance < min_km or actual_distance > max_km:
        return None

    return (new_lat, new_lon)


def _generate_frequent_destinations(
    home_lat: float, home_lon: float, count: int, min_km: float = 0.8, max_km: float = 20.0
) -> list[dict]:
    """Generate frequent destinations within min_km-max_km of home."""
    destinations: list[dict] = []

    for _ in range(count):
        coords = None
        for _ in range(10):  # Max 10 retries
            coords = _generate_destination_near(home_lat, home_lon, min_km, max_km)
            if coords:
                break

        if not coords:
            # Fallback: generate at minimum distance in random direction
            bearing = random.uniform(0, 2 * math.pi)
            delta_lat = (min_km * math.cos(bearing)) / 111.0
            delta_lon = (min_km * math.sin(bearing)) / (111.0 * math.cos(math.radians(home_lat)))
            coords = (home_lat + delta_lat, home_lon + delta_lon)

        # Random weight (will be normalized later)
        weight = random.uniform(0.1, 0.5)

        # Optional time affinity (50% chance)
        time_affinity = None
        if random.random() < 0.5:
            time_affinity = random.choice(TIME_AFFINITY_PATTERNS)

        destinations.append(
            {
                "coordinates": coords,
                "weight": weight,
                "time_affinity": time_affinity,
            }
        )

    # Normalize weights
    total_weight: float = sum(float(d["weight"]) for d in destinations)
    for d in destinations:
        d["weight"] = float(d["weight"]) / total_weight

    return destinations


def generate_rider_dna(faker: Faker | None = None) -> RiderDNA:
    """Generate random rider DNA with realistic Brazilian rider profile.

    Args:
        faker: Optional Faker instance. Uses module-level instance if not provided.
               Pass a seeded Faker for deterministic output.

    Returns:
        RiderDNA with randomly generated attributes.
    """
    fake = faker or _faker

    # Home location
    home_lat = random.uniform(SAO_PAULO_LAT_MIN, SAO_PAULO_LAT_MAX)
    home_lon = random.uniform(SAO_PAULO_LON_MIN, SAO_PAULO_LON_MAX)
    home_location = (home_lat, home_lon)

    # Behavioral parameters (immutable)
    # Behavior factor skewed toward higher values (most riders are well-behaved)
    behavior_factor = max(0.5, min(1.0, random.gauss(0.85, 0.15)))

    patience_threshold = random.randint(120, 300)
    max_surge_multiplier = random.uniform(1.5, 3.0)
    avg_rides_per_week = random.randint(1, 15)

    # Generate 2-5 frequent destinations
    num_destinations = random.randint(2, 5)
    frequent_destinations = _generate_frequent_destinations(home_lat, home_lon, num_destinations)

    # Personal info from Faker
    first_name = fake.first_name()
    last_name = fake.last_name()
    email = fake.email()
    phone = fake.phone_br_mobile_sp()

    # Payment method from Faker
    payment = fake.payment_method_br()
    payment_method_type = payment["type"]
    payment_method_masked = payment["masked"]

    return RiderDNA(
        behavior_factor=behavior_factor,
        patience_threshold=patience_threshold,
        max_surge_multiplier=max_surge_multiplier,
        avg_rides_per_week=avg_rides_per_week,
        frequent_destinations=frequent_destinations,
        home_location=home_location,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        payment_method_type=payment_method_type,
        payment_method_masked=payment_method_masked,
    )
