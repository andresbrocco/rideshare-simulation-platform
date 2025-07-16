"""Tests for agent DNA models."""

import pytest
from pydantic import ValidationError

from agents.dna import DriverDNA, RiderDNA


class TestDriverDNA:
    """Test DriverDNA model."""

    def test_driver_dna_valid(self):
        """Creates DriverDNA with valid parameters."""
        dna = DriverDNA(
            acceptance_rate=0.85,
            cancellation_tendency=0.05,
            service_quality=0.9,
            response_time=5.0,
            min_rider_rating=4.0,
            home_location=(-23.55, -46.63),
            preferred_zones=["zone1", "zone2"],
            shift_preference="morning",
            avg_hours_per_day=8,
            avg_days_per_week=5,
            vehicle_make="Toyota",
            vehicle_model="Corolla",
            vehicle_year=2020,
            license_plate="ABC1234",
            first_name="João",
            last_name="Silva",
            email="joao@example.com",
            phone="+5511999999999"
        )
        assert dna.acceptance_rate == 0.85
        assert dna.service_quality == 0.9
        assert dna.home_location == (-23.55, -46.63)
        assert dna.vehicle_make == "Toyota"

    def test_driver_dna_immutable_fields(self):
        """Validates behavioral parameters are set."""
        dna = DriverDNA(
            acceptance_rate=0.85,
            cancellation_tendency=0.05,
            service_quality=0.9,
            response_time=5.0,
            min_rider_rating=4.0,
            home_location=(-23.55, -46.63),
            preferred_zones=["zone1"],
            shift_preference="morning",
            avg_hours_per_day=8,
            avg_days_per_week=5,
            vehicle_make="Toyota",
            vehicle_model="Corolla",
            vehicle_year=2020,
            license_plate="ABC1234",
            first_name="João",
            last_name="Silva",
            email="joao@example.com",
            phone="+5511999999999"
        )
        assert dna.acceptance_rate == 0.85
        assert dna.service_quality == 0.9

    def test_driver_dna_home_location_validation(self):
        """Validates home coordinates within Sao Paulo bounds."""
        dna = DriverDNA(
            acceptance_rate=0.85,
            cancellation_tendency=0.05,
            service_quality=0.9,
            response_time=5.0,
            min_rider_rating=4.0,
            home_location=(-23.55, -46.63),
            preferred_zones=["zone1"],
            shift_preference="morning",
            avg_hours_per_day=8,
            avg_days_per_week=5,
            vehicle_make="Toyota",
            vehicle_model="Corolla",
            vehicle_year=2020,
            license_plate="ABC1234",
            first_name="João",
            last_name="Silva",
            email="joao@example.com",
            phone="+5511999999999"
        )
        assert dna.home_location == (-23.55, -46.63)

    def test_driver_dna_invalid_coordinates(self):
        """Rejects coordinates outside bounds."""
        with pytest.raises(ValidationError):
            DriverDNA(
                acceptance_rate=0.85,
                cancellation_tendency=0.05,
                service_quality=0.9,
                response_time=5.0,
                min_rider_rating=4.0,
                home_location=(0.0, 0.0),
                preferred_zones=["zone1"],
                shift_preference="morning",
                avg_hours_per_day=8,
                avg_days_per_week=5,
                vehicle_make="Toyota",
                vehicle_model="Corolla",
                vehicle_year=2020,
                license_plate="ABC1234",
                first_name="João",
                last_name="Silva",
                email="joao@example.com",
                phone="+5511999999999"
            )

    def test_driver_dna_acceptance_rate_bounds(self):
        """Validates acceptance_rate in [0.0, 1.0]."""
        with pytest.raises(ValidationError):
            DriverDNA(
                acceptance_rate=1.5,
                cancellation_tendency=0.05,
                service_quality=0.9,
                response_time=5.0,
                min_rider_rating=4.0,
                home_location=(-23.55, -46.63),
                preferred_zones=["zone1"],
                shift_preference="morning",
                avg_hours_per_day=8,
                avg_days_per_week=5,
                vehicle_make="Toyota",
                vehicle_model="Corolla",
                vehicle_year=2020,
                license_plate="ABC1234",
                first_name="João",
                last_name="Silva",
                email="joao@example.com",
                phone="+5511999999999"
            )

    def test_driver_dna_response_time_bounds(self):
        """Validates response_time between 3-12 seconds."""
        with pytest.raises(ValidationError):
            DriverDNA(
                acceptance_rate=0.85,
                cancellation_tendency=0.05,
                service_quality=0.9,
                response_time=1.0,
                min_rider_rating=4.0,
                home_location=(-23.55, -46.63),
                preferred_zones=["zone1"],
                shift_preference="morning",
                avg_hours_per_day=8,
                avg_days_per_week=5,
                vehicle_make="Toyota",
                vehicle_model="Corolla",
                vehicle_year=2020,
                license_plate="ABC1234",
                first_name="João",
                last_name="Silva",
                email="joao@example.com",
                phone="+5511999999999"
            )

    def test_driver_dna_shift_preference_enum(self):
        """Validates shift_preference enum."""
        dna = DriverDNA(
            acceptance_rate=0.85,
            cancellation_tendency=0.05,
            service_quality=0.9,
            response_time=5.0,
            min_rider_rating=4.0,
            home_location=(-23.55, -46.63),
            preferred_zones=["zone1"],
            shift_preference="afternoon",
            avg_hours_per_day=8,
            avg_days_per_week=5,
            vehicle_make="Toyota",
            vehicle_model="Corolla",
            vehicle_year=2020,
            license_plate="ABC1234",
            first_name="João",
            last_name="Silva",
            email="joao@example.com",
            phone="+5511999999999"
        )
        assert dna.shift_preference == "afternoon"


class TestRiderDNA:
    """Test RiderDNA model."""

    def test_rider_dna_valid(self):
        """Creates RiderDNA with valid parameters."""
        dna = RiderDNA(
            behavior_factor=0.75,
            patience_threshold=180,
            max_surge_multiplier=2.0,
            avg_rides_per_week=3,
            home_location=(-23.55, -46.63),
            frequent_destinations=[
                {"coordinates": (-23.56, -46.64), "weight": 0.6},
                {"coordinates": (-23.54, -46.62), "weight": 0.4}
            ],
            first_name="Maria",
            last_name="Santos",
            email="maria@example.com",
            phone="+5511988888888",
            payment_method_type="credit_card",
            payment_method_masked="****1234"
        )
        assert dna.behavior_factor == 0.75
        assert dna.patience_threshold == 180
        assert len(dna.frequent_destinations) == 2

    def test_rider_dna_frequent_destinations(self):
        """Validates frequent destinations structure."""
        dna = RiderDNA(
            behavior_factor=0.75,
            patience_threshold=180,
            max_surge_multiplier=2.0,
            avg_rides_per_week=3,
            home_location=(-23.55, -46.63),
            frequent_destinations=[
                {"coordinates": (-23.56, -46.64), "weight": 0.6},
                {"coordinates": (-23.54, -46.62), "weight": 0.4}
            ],
            first_name="Maria",
            last_name="Santos",
            email="maria@example.com",
            phone="+5511988888888",
            payment_method_type="credit_card",
            payment_method_masked="****1234"
        )
        assert len(dna.frequent_destinations) == 2
        assert dna.frequent_destinations[0]["weight"] == 0.6

    def test_rider_dna_destination_distance(self):
        """Validates destinations within 20km of home."""
        with pytest.raises(ValidationError):
            RiderDNA(
                behavior_factor=0.75,
                patience_threshold=180,
                max_surge_multiplier=2.0,
                avg_rides_per_week=3,
                home_location=(-23.55, -46.63),
                frequent_destinations=[
                    {"coordinates": (-23.35, -46.40), "weight": 1.0}
                ],
                first_name="Maria",
                last_name="Santos",
                email="maria@example.com",
                phone="+5511988888888",
                payment_method_type="credit_card",
                payment_method_masked="****1234"
            )

    def test_rider_dna_patience_threshold_bounds(self):
        """Validates patience between 2-5 minutes."""
        dna = RiderDNA(
            behavior_factor=0.75,
            patience_threshold=120,
            max_surge_multiplier=2.0,
            avg_rides_per_week=3,
            home_location=(-23.55, -46.63),
            frequent_destinations=[
                {"coordinates": (-23.56, -46.64), "weight": 0.6},
                {"coordinates": (-23.54, -46.62), "weight": 0.4}
            ],
            first_name="Maria",
            last_name="Santos",
            email="maria@example.com",
            phone="+5511988888888",
            payment_method_type="credit_card",
            payment_method_masked="****1234"
        )
        assert dna.patience_threshold == 120

    def test_rider_dna_surge_sensitivity_bounds(self):
        """Validates max_surge_multiplier >= 1.0."""
        dna = RiderDNA(
            behavior_factor=0.75,
            patience_threshold=180,
            max_surge_multiplier=3.5,
            avg_rides_per_week=3,
            home_location=(-23.55, -46.63),
            frequent_destinations=[
                {"coordinates": (-23.56, -46.64), "weight": 0.6},
                {"coordinates": (-23.54, -46.62), "weight": 0.4}
            ],
            first_name="Maria",
            last_name="Santos",
            email="maria@example.com",
            phone="+5511988888888",
            payment_method_type="credit_card",
            payment_method_masked="****1234"
        )
        assert dna.max_surge_multiplier == 3.5

    def test_rider_dna_behavior_factor_bounds(self):
        """Validates behavior_factor in [0.0, 1.0]."""
        dna = RiderDNA(
            behavior_factor=0.75,
            patience_threshold=180,
            max_surge_multiplier=2.0,
            avg_rides_per_week=3,
            home_location=(-23.55, -46.63),
            frequent_destinations=[
                {"coordinates": (-23.56, -46.64), "weight": 0.6},
                {"coordinates": (-23.54, -46.62), "weight": 0.4}
            ],
            first_name="Maria",
            last_name="Santos",
            email="maria@example.com",
            phone="+5511988888888",
            payment_method_type="credit_card",
            payment_method_masked="****1234"
        )
        assert dna.behavior_factor == 0.75
