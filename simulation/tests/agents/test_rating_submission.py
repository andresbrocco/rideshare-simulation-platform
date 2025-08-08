"""Tests for rating submission behavior after trip completion."""

import random
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
import simpy

from agents.dna import DriverDNA, RiderDNA, ShiftPreference
from agents.driver_agent import DriverAgent
from agents.rating_logic import generate_rating_value, should_submit_rating
from agents.rider_agent import RiderAgent
from trip import Trip, TripState


def create_driver_dna(service_quality: float = 0.7) -> DriverDNA:
    return DriverDNA(
        acceptance_rate=0.85,
        cancellation_tendency=0.05,
        service_quality=service_quality,
        response_time=5.0,
        min_rider_rating=3.5,
        surge_acceptance_modifier=1.3,
        home_location=(-23.55, -46.63),
        preferred_zones=["centro", "pinheiros"],
        shift_preference=ShiftPreference.MORNING,
        avg_hours_per_day=8,
        avg_days_per_week=5,
        vehicle_make="Toyota",
        vehicle_model="Corolla",
        vehicle_year=2020,
        license_plate="ABC-1234",
        first_name="Carlos",
        last_name="Silva",
        email="carlos@example.com",
        phone="+5511999999999",
    )


def create_rider_dna(behavior_factor: float = 0.7) -> RiderDNA:
    return RiderDNA(
        behavior_factor=behavior_factor,
        patience_threshold=180,
        max_surge_multiplier=2.0,
        avg_rides_per_week=10,
        frequent_destinations=[
            {"coordinates": (-23.56, -46.64), "weight": 0.6},
            {"coordinates": (-23.57, -46.65), "weight": 0.4},
        ],
        home_location=(-23.55, -46.63),
        first_name="Maria",
        last_name="Santos",
        email="maria@example.com",
        phone="+5511888888888",
        payment_method_type="credit_card",
        payment_method_masked="**** 1234",
    )


def create_trip(trip_id: str = "trip-1", state: TripState = TripState.COMPLETED) -> Trip:
    trip = Trip(
        trip_id=trip_id,
        rider_id="rider-1",
        driver_id="driver-1",
        pickup_location=(-23.55, -46.63),
        dropoff_location=(-23.56, -46.64),
        pickup_zone_id="zone-1",
        dropoff_zone_id="zone-2",
        surge_multiplier=1.0,
        fare=25.0,
    )
    trip.state = state
    return trip


class TestRatingOnlyForCompletedTrips:
    def test_no_rating_for_cancelled_trip(self):
        """Ratings should only be submitted for completed trips."""
        env = simpy.Environment()
        driver = DriverAgent("driver-1", create_driver_dna(), env, None)
        rider = RiderAgent("rider-1", create_rider_dna(), env, None)

        trip = create_trip(state=TripState.CANCELLED)

        driver_rating = driver.submit_rating_for_trip(trip, rider)
        rider_rating = rider.submit_rating_for_trip(trip, driver)

        assert driver_rating is None
        assert rider_rating is None


class TestSubmissionProbability:
    def test_neutral_submission_rate(self):
        """~60% submission rate for neutral trip experiences (ratings 3-4)."""
        random.seed(42)
        submissions = 0
        total = 100

        for _ in range(total):
            rating_value = 4
            if should_submit_rating(rating_value):
                submissions += 1

        assert 50 <= submissions <= 70

    def test_exceptional_submission_rate(self):
        """~85% submission rate for exceptional experiences (ratings 1-2 or 5)."""
        random.seed(42)
        submissions = 0
        total = 100

        for _ in range(total):
            rating_value = 5
            if should_submit_rating(rating_value):
                submissions += 1

        assert 75 <= submissions <= 95

    def test_overall_submission_rate(self):
        """Overall submission rate should be ~65-70%."""
        random.seed(42)
        submissions = 0
        total = 1000

        rating_distribution = [3] * 200 + [4] * 400 + [5] * 300 + [2] * 80 + [1] * 20

        for rating in rating_distribution:
            if should_submit_rating(rating):
                submissions += 1

        rate = submissions / total
        assert 0.60 <= rate <= 0.80


class TestDriverRatesRider:
    def test_driver_rates_rider_emits_event(self):
        """Driver submits rating for rider and emits rating event."""
        env = simpy.Environment()
        mock_producer = MagicMock()
        driver = DriverAgent("driver-1", create_driver_dna(), env, mock_producer)
        rider = RiderAgent("rider-1", create_rider_dna(behavior_factor=0.9), env, None)

        trip = create_trip()

        random.seed(42)
        rating = driver.submit_rating_for_trip(trip, rider)

        if rating is not None:
            assert mock_producer.produce.called
            call_args = mock_producer.produce.call_args
            assert call_args.kwargs["topic"] == "ratings"


class TestRiderRatesDriver:
    def test_rider_rates_driver_emits_event(self):
        """Rider submits rating for driver and emits rating event."""
        env = simpy.Environment()
        mock_producer = MagicMock()
        rider = RiderAgent("rider-1", create_rider_dna(), env, mock_producer)
        driver = DriverAgent("driver-1", create_driver_dna(service_quality=0.9), env, None)

        trip = create_trip()

        random.seed(42)
        rating = rider.submit_rating_for_trip(trip, driver)

        if rating is not None:
            assert mock_producer.produce.called
            call_args = mock_producer.produce.call_args
            assert call_args.kwargs["topic"] == "ratings"


class TestRatingValueBasedOnDNA:
    def test_high_behavior_factor_yields_higher_ratings(self):
        """High behavior_factor riders should receive higher ratings from drivers."""
        random.seed(42)
        ratings_high = []
        ratings_low = []

        for _ in range(100):
            rating_high = generate_rating_value(0.9, "behavior_factor")
            rating_low = generate_rating_value(0.2, "behavior_factor")
            ratings_high.append(rating_high)
            ratings_low.append(rating_low)

        mean_high = sum(ratings_high) / len(ratings_high)
        mean_low = sum(ratings_low) / len(ratings_low)

        assert mean_high > mean_low
        assert mean_high >= 4.3
        assert mean_low <= 4.0

    def test_high_service_quality_yields_higher_ratings(self):
        """High service_quality drivers should receive higher ratings from riders."""
        random.seed(42)
        ratings_high = []
        ratings_low = []

        for _ in range(100):
            rating_high = generate_rating_value(0.9, "service_quality")
            rating_low = generate_rating_value(0.2, "service_quality")
            ratings_high.append(rating_high)
            ratings_low.append(rating_low)

        mean_high = sum(ratings_high) / len(ratings_high)
        mean_low = sum(ratings_low) / len(ratings_low)

        assert mean_high > mean_low
        assert mean_high >= 4.2
        assert mean_low <= 4.0


class TestRatingValueDistribution:
    def test_high_quality_dna_rating_distribution(self):
        """High quality DNA should yield higher mean ratings."""
        random.seed(42)
        ratings = [generate_rating_value(0.95, "service_quality") for _ in range(100)]
        mean_rating = sum(ratings) / len(ratings)

        assert 4.3 <= mean_rating <= 5.0

    def test_low_quality_dna_rating_distribution(self):
        """Low quality DNA should yield lower mean ratings."""
        random.seed(42)
        ratings = [generate_rating_value(0.2, "service_quality") for _ in range(100)]
        mean_rating = sum(ratings) / len(ratings)

        assert 3.0 <= mean_rating <= 4.2


class TestRatingValueRange:
    def test_rating_values_are_valid(self):
        """All rating values should be integers between 1 and 5."""
        random.seed(42)

        for dna_value in [0.1, 0.3, 0.5, 0.7, 0.9]:
            for _ in range(50):
                rating = generate_rating_value(dna_value, "behavior_factor")
                assert isinstance(rating, int)
                assert 1 <= rating <= 5

                rating = generate_rating_value(dna_value, "service_quality")
                assert isinstance(rating, int)
                assert 1 <= rating <= 5


class TestRatingEventEmission:
    def test_rating_event_has_correct_fields(self):
        """Rating event should contain all required fields."""
        env = simpy.Environment()
        mock_producer = MagicMock()
        driver = DriverAgent("driver-1", create_driver_dna(), env, mock_producer)
        rider = RiderAgent("rider-1", create_rider_dna(behavior_factor=0.95), env, None)

        trip = create_trip()

        random.seed(1)
        rating = driver.submit_rating_for_trip(trip, rider)

        if rating is not None:
            call_args = mock_producer.produce.call_args
            event = call_args.kwargs["value"]
            assert event.trip_id == "trip-1"
            assert event.rater_type == "driver"
            assert event.rater_id == "driver-1"
            assert event.ratee_type == "rider"
            assert event.ratee_id == "rider-1"
            assert 1 <= event.rating <= 5


class TestAgentRatingUpdates:
    def test_agent_rating_count_increments(self):
        """Agent's rating_count should increment when receiving a rating."""
        env = simpy.Environment()
        driver = DriverAgent("driver-1", create_driver_dna(), env, None)

        initial_count = driver.rating_count
        driver.update_rating(4)

        assert driver.rating_count == initial_count + 1

    def test_agent_current_rating_updates(self):
        """Agent's current_rating should be recalculated with running average."""
        env = simpy.Environment()
        driver = DriverAgent("driver-1", create_driver_dna(), env, None)

        assert driver.current_rating == 5.0
        assert driver.rating_count == 0

        driver.update_rating(4)
        assert driver.current_rating == pytest.approx(4.0, rel=0.01)
        assert driver.rating_count == 1

        driver.update_rating(3)
        expected = (4.0 + 3) / 2
        assert driver.current_rating == pytest.approx(expected, rel=0.01)
        assert driver.rating_count == 2


class TestIndependentSubmission:
    def test_driver_and_rider_submit_independently(self):
        """Driver and rider should make independent submission decisions."""
        env = simpy.Environment()
        mock_producer = MagicMock()

        driver = DriverAgent("driver-1", create_driver_dna(), env, mock_producer)
        rider = RiderAgent("rider-1", create_rider_dna(), env, mock_producer)

        trip = create_trip()

        random.seed(42)

        driver_submissions = 0
        rider_submissions = 0

        for i in range(100):
            random.seed(i)
            driver_rating = driver.submit_rating_for_trip(trip, rider)
            rider_rating = rider.submit_rating_for_trip(trip, driver)

            if driver_rating is not None:
                driver_submissions += 1
            if rider_rating is not None:
                rider_submissions += 1

        assert 40 <= driver_submissions <= 90
        assert 40 <= rider_submissions <= 90
