"""Test factories for generating synthetic test data with deterministic Faker."""

from __future__ import annotations

import random
from typing import Any

from agents.dna import DriverDNA, RiderDNA, ShiftPreference
from agents.faker_provider import create_faker_instance


class DNAFactory:
    """Factory for creating DNA objects with deterministic Faker data."""

    DEFAULT_SEED = 42

    def __init__(self, seed: int = DEFAULT_SEED):
        """Initialize factory with seeded Faker instance.

        Args:
            seed: Random seed for reproducible test data.
        """
        self.seed = seed
        self.fake = create_faker_instance(seed)
        # Also seed Python's random for non-Faker fields
        random.seed(seed)

    def driver_dna(self, **overrides: Any) -> DriverDNA:
        """Create a DriverDNA with Faker-generated personal data.

        Args:
            **overrides: Override any field with specific values.

        Returns:
            DriverDNA instance with defaults or overridden values.
        """
        vehicle = self.fake.vehicle_br()

        defaults: dict[str, Any] = {
            # Behavioral parameters
            "acceptance_rate": 0.85,
            "cancellation_tendency": 0.05,
            "service_quality": 0.9,
            "response_time": 5.0,
            "min_rider_rating": 3.5,
            "surge_acceptance_modifier": 1.5,
            # Profile attributes
            # Coordinates inside BVI zone from sample_zones.geojson
            "home_location": (-23.56, -46.65),
            "shift_preference": ShiftPreference.MORNING,
            "avg_hours_per_day": 8,
            "avg_days_per_week": 5,
            "vehicle_make": vehicle["make"],
            "vehicle_model": vehicle["model"],
            "vehicle_year": vehicle["year"],
            "license_plate": self.fake.license_plate_br(),
            "first_name": self.fake.first_name(),
            "last_name": self.fake.last_name(),
            "email": self.fake.email(),
            "phone": self.fake.phone_br_mobile_sp(),
        }
        defaults.update(overrides)
        return DriverDNA(**defaults)

    def rider_dna(self, **overrides: Any) -> RiderDNA:
        """Create a RiderDNA with Faker-generated personal data.

        Args:
            **overrides: Override any field with specific values.

        Returns:
            RiderDNA instance with defaults or overridden values.
        """
        # Default home in BVI zone from sample_zones.geojson
        home_location = overrides.get("home_location", (-23.56, -46.65))

        payment = self.fake.payment_method_br()

        defaults: dict[str, Any] = {
            # Behavioral parameters
            "behavior_factor": 0.75,
            "patience_threshold": 180,
            "max_surge_multiplier": 2.0,
            "avg_rides_per_week": 5,
            # Destinations in PIN and SEE zones from sample_zones.geojson
            "frequent_destinations": [
                {"coordinates": (-23.565, -46.695), "weight": 0.6},  # Inside PIN
                {"coordinates": (-23.55, -46.635), "weight": 0.4},  # Inside SEE
            ],
            # Profile attributes
            "home_location": home_location,
            "first_name": self.fake.first_name(),
            "last_name": self.fake.last_name(),
            "email": self.fake.email(),
            "phone": self.fake.phone_br_mobile_sp(),
            "payment_method_type": payment["type"],
            "payment_method_masked": payment["masked"],
        }
        defaults.update(overrides)
        return RiderDNA(**defaults)

    def driver_dna_batch(self, count: int, **common_overrides: Any) -> list[DriverDNA]:
        """Create multiple DriverDNA objects.

        Args:
            count: Number of DNA objects to create.
            **common_overrides: Fields to override for all objects.

        Returns:
            List of DriverDNA instances.
        """
        return [self.driver_dna(**common_overrides) for _ in range(count)]

    def rider_dna_batch(self, count: int, **common_overrides: Any) -> list[RiderDNA]:
        """Create multiple RiderDNA objects.

        Args:
            count: Number of DNA objects to create.
            **common_overrides: Fields to override for all objects.

        Returns:
            List of RiderDNA instances.
        """
        return [self.rider_dna(**common_overrides) for _ in range(count)]
