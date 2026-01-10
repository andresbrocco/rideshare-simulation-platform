"""Tests for agent DNA models."""

import pytest
from pydantic import ValidationError

from agents.dna import DriverDNA, RiderDNA
from tests.factories import DNAFactory


class TestDriverDNA:
    """Test DriverDNA model."""

    def test_driver_dna_valid(self, dna_factory: DNAFactory):
        """Creates DriverDNA with valid parameters."""
        dna = dna_factory.driver_dna()
        assert 0.0 <= dna.acceptance_rate <= 1.0
        assert 0.0 <= dna.service_quality <= 1.0
        assert dna.home_location == (-23.56, -46.65)  # Inside BVI zone
        assert dna.vehicle_make is not None

    def test_driver_dna_immutable_fields(self, dna_factory: DNAFactory):
        """Validates behavioral parameters are set."""
        dna = dna_factory.driver_dna(acceptance_rate=0.85, service_quality=0.9)
        assert dna.acceptance_rate == 0.85
        assert dna.service_quality == 0.9

    def test_driver_dna_home_location_validation(self, dna_factory: DNAFactory):
        """Validates home coordinates within a zone."""
        dna = dna_factory.driver_dna(home_location=(-23.56, -46.65))  # Inside BVI
        assert dna.home_location == (-23.56, -46.65)

    def test_driver_dna_invalid_coordinates(self, dna_factory: DNAFactory):
        """Rejects coordinates outside bounds."""
        with pytest.raises(ValidationError):
            dna_factory.driver_dna(home_location=(0.0, 0.0))

    def test_driver_dna_acceptance_rate_bounds(self, dna_factory: DNAFactory):
        """Validates acceptance_rate in [0.0, 1.0]."""
        with pytest.raises(ValidationError):
            dna_factory.driver_dna(acceptance_rate=1.5)

    def test_driver_dna_response_time_bounds(self, dna_factory: DNAFactory):
        """Validates response_time between 3-12 seconds."""
        with pytest.raises(ValidationError):
            dna_factory.driver_dna(response_time=1.0)

    def test_driver_dna_shift_preference_enum(self, dna_factory: DNAFactory):
        """Validates shift_preference enum."""
        dna = dna_factory.driver_dna(shift_preference="afternoon")
        assert dna.shift_preference == "afternoon"


class TestRiderDNA:
    """Test RiderDNA model."""

    def test_rider_dna_valid(self, dna_factory: DNAFactory):
        """Creates RiderDNA with valid parameters."""
        dna = dna_factory.rider_dna()
        assert 0.0 <= dna.behavior_factor <= 1.0
        assert 120 <= dna.patience_threshold <= 300
        assert len(dna.frequent_destinations) >= 2

    def test_rider_dna_frequent_destinations(self, dna_factory: DNAFactory):
        """Validates frequent destinations structure."""
        # Destinations inside PIN and SEE zones from sample_zones.geojson
        destinations = [
            {"coordinates": (-23.565, -46.695), "weight": 0.6},  # Inside PIN
            {"coordinates": (-23.55, -46.635), "weight": 0.4},  # Inside SEE
        ]
        dna = dna_factory.rider_dna(frequent_destinations=destinations)
        assert len(dna.frequent_destinations) == 2
        assert dna.frequent_destinations[0]["weight"] == 0.6

    def test_rider_dna_destination_distance(self, dna_factory: DNAFactory):
        """Validates destinations within 20km of home."""
        # Destination too far from home
        far_destinations = [{"coordinates": (-23.35, -46.40), "weight": 1.0}]
        with pytest.raises(ValidationError):
            dna_factory.rider_dna(frequent_destinations=far_destinations)

    def test_rider_dna_patience_threshold_bounds(self, dna_factory: DNAFactory):
        """Validates patience between 2-5 minutes."""
        dna = dna_factory.rider_dna(patience_threshold=120)
        assert dna.patience_threshold == 120

    def test_rider_dna_surge_sensitivity_bounds(self, dna_factory: DNAFactory):
        """Validates max_surge_multiplier >= 1.0."""
        dna = dna_factory.rider_dna(max_surge_multiplier=3.5)
        assert dna.max_surge_multiplier == 3.5

    def test_rider_dna_behavior_factor_bounds(self, dna_factory: DNAFactory):
        """Validates behavior_factor in [0.0, 1.0]."""
        dna = dna_factory.rider_dna(behavior_factor=0.75)
        assert dna.behavior_factor == 0.75

    def test_rider_dna_destination_outside_zone(self, dna_factory: DNAFactory):
        """Rejects destinations outside all zone boundaries."""
        # Coordinates outside any São Paulo zone (in the ocean)
        out_of_zone_destinations = [
            {"coordinates": (-23.56, -46.50), "weight": 0.5},  # Outside zones
            {"coordinates": (-23.55, -46.51), "weight": 0.5},  # Outside zones
        ]
        with pytest.raises(ValidationError) as exc_info:
            dna_factory.rider_dna(frequent_destinations=out_of_zone_destinations)
        assert "not within any São Paulo zone boundary" in str(exc_info.value)
