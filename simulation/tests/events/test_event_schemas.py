from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from events.schemas import (
    DriverProfileEvent,
    DriverStatusEvent,
    GPSPingEvent,
    PaymentEvent,
    RatingEvent,
    RiderProfileEvent,
    SurgeUpdateEvent,
    TripEvent,
)


class TestTripEvent:
    def test_trip_event_valid(self):
        event = TripEvent(
            event_type="trip.requested",
            trip_id="123e4567-e89b-12d3-a456-426614174000",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id=None,
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.5,
            fare=25.50,
        )
        assert event.event_type == "trip.requested"
        assert event.trip_id == "123e4567-e89b-12d3-a456-426614174000"
        assert event.driver_id is None

    def test_trip_event_auto_uuid(self):
        event = TripEvent(
            event_type="trip.requested",
            trip_id="123e4567-e89b-12d3-a456-426614174000",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id=None,
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.5,
            fare=25.50,
        )
        assert event.event_id is not None
        UUID(str(event.event_id))

    def test_trip_event_timestamp_utc(self):
        event = TripEvent(
            event_type="trip.requested",
            trip_id="123e4567-e89b-12d3-a456-426614174000",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id=None,
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.5,
            fare=25.50,
        )
        assert event.timestamp == "2025-07-17T10:30:00Z"

    def test_trip_event_serialization(self):
        event = TripEvent(
            event_type="trip.requested",
            trip_id="123e4567-e89b-12d3-a456-426614174000",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id=None,
            pickup_location=(40.7128, -74.0060),
            dropoff_location=(40.7580, -73.9855),
            pickup_zone_id="zone_A",
            dropoff_zone_id="zone_B",
            surge_multiplier=1.5,
            fare=25.50,
        )
        data = event.model_dump(mode="json")
        assert isinstance(data, dict)
        assert data["event_type"] == "trip.requested"
        assert data["pickup_location"] == [40.7128, -74.0060]


class TestGPSPingEvent:
    def test_gps_ping_event_driver(self):
        event = GPSPingEvent(
            entity_type="driver",
            entity_id="driver_001",
            timestamp="2025-07-17T10:30:00Z",
            location=(-23.5505, -46.6333),
            heading=45.0,
            speed=30.5,
            accuracy=5.0,
            trip_id="123e4567-e89b-12d3-a456-426614174000",
        )
        assert event.entity_type == "driver"
        assert event.heading == 45.0
        assert event.speed == 30.5

    def test_gps_ping_event_rider_stationary(self):
        event = GPSPingEvent(
            entity_type="rider",
            entity_id="rider_001",
            timestamp="2025-07-17T10:30:00Z",
            location=(-23.5505, -46.6333),
            heading=None,
            speed=None,
            accuracy=5.0,
            trip_id=None,
        )
        assert event.entity_type == "rider"
        assert event.heading is None
        assert event.speed is None

    def test_gps_ping_invalid_entity_type(self):
        with pytest.raises(ValidationError):
            GPSPingEvent(
                entity_type="passenger",
                entity_id="rider_001",
                timestamp="2025-07-17T10:30:00Z",
                location=(-23.5505, -46.6333),
                heading=None,
                speed=None,
                accuracy=5.0,
                trip_id=None,
            )


class TestDriverStatusEvent:
    def test_driver_status_event_valid(self):
        event = DriverStatusEvent(
            driver_id="driver_001",
            timestamp="2025-07-17T10:30:00Z",
            previous_status="online",
            new_status="en_route_pickup",
            trigger="trip_accepted",
            location=(-23.5505, -46.6333),
        )
        assert event.driver_id == "driver_001"
        assert event.new_status == "en_route_pickup"

    def test_driver_status_valid_statuses(self):
        event = DriverStatusEvent(
            driver_id="driver_001",
            timestamp="2025-07-17T10:30:00Z",
            previous_status=None,
            new_status="online",
            trigger="shift_start",
            location=(-23.5505, -46.6333),
        )
        assert event.new_status == "online"
        assert event.previous_status is None


class TestSurgeUpdateEvent:
    def test_surge_update_event_valid(self):
        event = SurgeUpdateEvent(
            zone_id="zone_A",
            timestamp="2025-07-17T10:30:00Z",
            previous_multiplier=1.0,
            new_multiplier=1.5,
            available_drivers=5,
            pending_requests=15,
            calculation_window_seconds=60,
        )
        assert event.zone_id == "zone_A"
        assert event.new_multiplier == 1.5


class TestRatingEvent:
    def test_rating_event_valid(self):
        event = RatingEvent(
            trip_id="123e4567-e89b-12d3-a456-426614174000",
            timestamp="2025-07-17T10:30:00Z",
            rater_type="rider",
            rater_id="rider_001",
            ratee_type="driver",
            ratee_id="driver_001",
            rating=5,
        )
        assert event.rating == 5
        assert event.rater_type == "rider"

    def test_rating_value_bounds(self):
        with pytest.raises(ValidationError):
            RatingEvent(
                trip_id="123e4567-e89b-12d3-a456-426614174000",
                timestamp="2025-07-17T10:30:00Z",
                rater_type="rider",
                rater_id="rider_001",
                ratee_type="driver",
                ratee_id="driver_001",
                rating=6,
            )


class TestPaymentEvent:
    def test_payment_event_valid(self):
        event = PaymentEvent(
            payment_id="123e4567-e89b-12d3-a456-426614174000",
            trip_id="123e4567-e89b-12d3-a456-426614174000",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id="driver_001",
            payment_method_type="credit_card",
            payment_method_masked="****1234",
            fare_amount=100.00,
            platform_fee_percentage=0.25,
            platform_fee_amount=25.00,
            driver_payout_amount=75.00,
        )
        assert event.fare_amount == 100.00
        assert event.platform_fee_percentage == 0.25

    def test_payment_fee_calculation(self):
        event = PaymentEvent(
            payment_id="123e4567-e89b-12d3-a456-426614174000",
            trip_id="123e4567-e89b-12d3-a456-426614174000",
            timestamp="2025-07-17T10:30:00Z",
            rider_id="rider_001",
            driver_id="driver_001",
            payment_method_type="credit_card",
            payment_method_masked="****1234",
            fare_amount=100.00,
            platform_fee_percentage=0.25,
            platform_fee_amount=25.00,
            driver_payout_amount=75.00,
        )
        assert event.fare_amount == 100.00
        assert event.platform_fee_amount == 25.00
        assert event.driver_payout_amount == 75.00


class TestDriverProfileEvent:
    def test_driver_profile_event_created(self):
        event = DriverProfileEvent(
            event_type="driver.created",
            driver_id="driver_001",
            timestamp="2025-07-17T10:30:00Z",
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            phone="+55-11-98765-4321",
            home_location=(-23.5505, -46.6333),
            preferred_zones=["zone_A", "zone_B"],
            shift_preference="morning",
            vehicle_make="Toyota",
            vehicle_model="Corolla",
            vehicle_year=2022,
            license_plate="ABC-1234",
        )
        assert event.event_type == "driver.created"
        assert event.driver_id == "driver_001"


class TestRiderProfileEvent:
    def test_rider_profile_event_updated(self):
        event = RiderProfileEvent(
            event_type="rider.updated",
            rider_id="rider_001",
            timestamp="2025-07-17T10:30:00Z",
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="+55-11-98765-4321",
            home_location=(-23.5505, -46.6333),
            payment_method_type="credit_card",
            payment_method_masked="****5678",
            behavior_factor=None,
        )
        assert event.event_type == "rider.updated"
        assert event.rider_id == "rider_001"
        assert event.behavior_factor is None
