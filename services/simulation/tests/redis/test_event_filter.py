from datetime import datetime

import pytest

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
from pubsub.channels import (
    CHANNEL_DRIVER_UPDATES,
    CHANNEL_RIDER_UPDATES,
    CHANNEL_SURGE_UPDATES,
    CHANNEL_TRIP_UPDATES,
    DriverUpdateMessage,
    RiderUpdateMessage,
    SurgeUpdateMessage,
    TripUpdateMessage,
)
from redis_client.filter import EventFilter


@pytest.fixture
def event_filter():
    return EventFilter()


@pytest.fixture
def timestamp():
    return datetime.now().isoformat()


def test_gps_ping_driver_should_publish(event_filter, timestamp):
    event = GPSPingEvent(
        entity_type="driver",
        entity_id="driver-1",
        timestamp=timestamp,
        location=(-23.5505, -46.6333),
        heading=90.0,
        speed=30.0,
        accuracy=5.0,
        trip_id="trip-123",
    )
    assert event_filter.should_publish(event) is True


def test_gps_ping_rider_should_publish(event_filter, timestamp):
    event = GPSPingEvent(
        entity_type="rider",
        entity_id="rider-1",
        timestamp=timestamp,
        location=(-23.5505, -46.6333),
        heading=None,
        speed=30.0,
        accuracy=5.0,
        trip_id="trip-123",
    )
    assert event_filter.should_publish(event) is True


def test_gps_ping_transform_reduced_fields(event_filter, timestamp):
    event = GPSPingEvent(
        entity_type="driver",
        entity_id="driver-1",
        timestamp=timestamp,
        location=(-23.5505, -46.6333),
        heading=90.0,
        speed=30.0,
        accuracy=5.0,
        trip_id="trip-123",
    )
    channel, message = event_filter.transform(event)
    assert isinstance(message, DriverUpdateMessage)
    assert message.driver_id == "driver-1"
    assert message.location == (-23.5505, -46.6333)
    assert message.heading == 90.0
    assert message.trip_id == "trip-123"


def test_trip_requested_should_publish(event_filter, timestamp):
    event = TripEvent(
        event_type="trip.requested",
        trip_id="trip-1",
        timestamp=timestamp,
        rider_id="rider-1",
        driver_id=None,
        pickup_location=(-23.5505, -46.6333),
        dropoff_location=(-23.5600, -46.6400),
        pickup_zone_id="zone-1",
        dropoff_zone_id="zone-2",
        surge_multiplier=1.2,
        fare=25.50,
    )
    assert event_filter.should_publish(event) is True


def test_trip_matched_should_publish(event_filter, timestamp):
    event = TripEvent(
        event_type="trip.matched",
        trip_id="trip-1",
        timestamp=timestamp,
        rider_id="rider-1",
        driver_id="driver-1",
        pickup_location=(-23.5505, -46.6333),
        dropoff_location=(-23.5600, -46.6400),
        pickup_zone_id="zone-1",
        dropoff_zone_id="zone-2",
        surge_multiplier=1.2,
        fare=25.50,
    )
    assert event_filter.should_publish(event) is True


def test_trip_offer_sent_should_not_publish(event_filter, timestamp):
    event = TripEvent(
        event_type="trip.offer_sent",
        trip_id="trip-1",
        timestamp=timestamp,
        rider_id="rider-1",
        driver_id="driver-1",
        pickup_location=(-23.5505, -46.6333),
        dropoff_location=(-23.5600, -46.6400),
        pickup_zone_id="zone-1",
        dropoff_zone_id="zone-2",
        surge_multiplier=1.2,
        fare=25.50,
        offer_sequence=1,
    )
    assert event_filter.should_publish(event) is False


def test_trip_offer_expired_should_not_publish(event_filter, timestamp):
    event = TripEvent(
        event_type="trip.offer_expired",
        trip_id="trip-1",
        timestamp=timestamp,
        rider_id="rider-1",
        driver_id="driver-1",
        pickup_location=(-23.5505, -46.6333),
        dropoff_location=(-23.5600, -46.6400),
        pickup_zone_id="zone-1",
        dropoff_zone_id="zone-2",
        surge_multiplier=1.2,
        fare=25.50,
        offer_sequence=1,
    )
    assert event_filter.should_publish(event) is False


def test_trip_offer_rejected_should_not_publish(event_filter, timestamp):
    event = TripEvent(
        event_type="trip.offer_rejected",
        trip_id="trip-1",
        timestamp=timestamp,
        rider_id="rider-1",
        driver_id="driver-1",
        pickup_location=(-23.5505, -46.6333),
        dropoff_location=(-23.5600, -46.6400),
        pickup_zone_id="zone-1",
        dropoff_zone_id="zone-2",
        surge_multiplier=1.2,
        fare=25.50,
        offer_sequence=1,
    )
    assert event_filter.should_publish(event) is False


def test_driver_status_should_publish(event_filter, timestamp):
    event = DriverStatusEvent(
        driver_id="driver-1",
        timestamp=timestamp,
        previous_status="online",
        new_status="en_route_pickup",
        trigger="trip_matched",
        location=(-23.5505, -46.6333),
    )
    assert event_filter.should_publish(event) is True


def test_surge_update_should_publish(event_filter, timestamp):
    event = SurgeUpdateEvent(
        zone_id="zone-1",
        timestamp=timestamp,
        previous_multiplier=1.0,
        new_multiplier=1.5,
        available_drivers=10,
        pending_requests=20,
    )
    assert event_filter.should_publish(event) is True


def test_rating_event_should_not_publish(event_filter, timestamp):
    event = RatingEvent(
        trip_id="trip-1",
        timestamp=timestamp,
        rater_type="rider",
        rater_id="rider-1",
        ratee_type="driver",
        ratee_id="driver-1",
        rating=5,
        current_rating=4.8,
        rating_count=10,
    )
    assert event_filter.should_publish(event) is False


def test_payment_event_should_not_publish(event_filter, timestamp):
    event = PaymentEvent(
        payment_id="pay-1",
        trip_id="trip-1",
        timestamp=timestamp,
        rider_id="rider-1",
        driver_id="driver-1",
        payment_method_type="credit_card",
        payment_method_masked="****1234",
        fare_amount=25.50,
        platform_fee_percentage=0.25,
        platform_fee_amount=6.38,
        driver_payout_amount=19.12,
    )
    assert event_filter.should_publish(event) is False


def test_driver_profile_event_should_publish(event_filter, timestamp):
    """Driver profile events should be published for immediate map visibility."""
    event = DriverProfileEvent(
        event_type="driver.created",
        driver_id="driver-1",
        timestamp=timestamp,
        first_name="João",
        last_name="Silva",
        email="joao@example.com",
        phone="+5511987654321",
        home_location=(-23.5505, -46.6333),
        preferred_zones=["zone-1", "zone-2"],
        shift_preference="morning",
        vehicle_make="Toyota",
        vehicle_model="Corolla",
        vehicle_year=2020,
        license_plate="ABC-1234",
    )
    assert event_filter.should_publish(event) is True


def test_rider_profile_event_should_publish(event_filter, timestamp):
    """Rider profile events should be published for immediate map visibility."""
    event = RiderProfileEvent(
        event_type="rider.created",
        rider_id="rider-1",
        timestamp=timestamp,
        first_name="Maria",
        last_name="Santos",
        email="maria@example.com",
        phone="+5511912345678",
        home_location=(-23.5600, -46.6400),
        payment_method_type="credit_card",
        payment_method_masked="****1234",
    )
    assert event_filter.should_publish(event) is True


def test_transform_gps_to_driver_update(event_filter, timestamp):
    event_with_trip = GPSPingEvent(
        entity_type="driver",
        entity_id="driver-1",
        timestamp=timestamp,
        location=(-23.5505, -46.6333),
        heading=90.0,
        speed=30.0,
        accuracy=5.0,
        trip_id="trip-123",
    )
    channel, message = event_filter.transform(event_with_trip)
    assert channel == CHANNEL_DRIVER_UPDATES
    assert isinstance(message, DriverUpdateMessage)
    assert message.driver_id == "driver-1"
    assert message.location == (-23.5505, -46.6333)
    assert message.heading == 90.0
    assert message.status == "en_route_pickup"
    assert message.trip_id == "trip-123"
    assert message.timestamp == timestamp

    event_without_trip = GPSPingEvent(
        entity_type="driver",
        entity_id="driver-2",
        timestamp=timestamp,
        location=(-23.5505, -46.6333),
        heading=180.0,
        speed=10.0,
        accuracy=5.0,
        trip_id=None,
    )
    channel, message = event_filter.transform(event_without_trip)
    assert channel == CHANNEL_DRIVER_UPDATES
    assert message.status == "online"
    assert message.trip_id is None


def test_transform_trip_to_trip_update(event_filter, timestamp):
    event = TripEvent(
        event_type="trip.matched",
        trip_id="trip-1",
        timestamp=timestamp,
        rider_id="rider-1",
        driver_id="driver-1",
        pickup_location=(-23.5505, -46.6333),
        dropoff_location=(-23.5600, -46.6400),
        pickup_zone_id="zone-1",
        dropoff_zone_id="zone-2",
        surge_multiplier=1.2,
        fare=25.50,
    )
    channel, message = event_filter.transform(event)
    assert channel == CHANNEL_TRIP_UPDATES
    assert isinstance(message, TripUpdateMessage)
    assert message.trip_id == "trip-1"
    assert message.state == "matched"
    assert message.pickup == (-23.5505, -46.6333)
    assert message.dropoff == (-23.5600, -46.6400)
    assert message.driver_id == "driver-1"
    assert message.rider_id == "rider-1"
    assert message.fare == 25.50
    assert message.surge_multiplier == 1.2
    assert message.timestamp == timestamp


def test_transform_driver_profile_to_driver_update(event_filter, timestamp):
    """Driver profile events should transform to DriverUpdateMessage at home location."""
    event = DriverProfileEvent(
        event_type="driver.created",
        driver_id="driver-1",
        timestamp=timestamp,
        first_name="João",
        last_name="Silva",
        email="joao@example.com",
        phone="+5511987654321",
        home_location=(-23.5505, -46.6333),
        preferred_zones=["zone-1", "zone-2"],
        shift_preference="morning",
        vehicle_make="Toyota",
        vehicle_model="Corolla",
        vehicle_year=2020,
        license_plate="ABC-1234",
    )
    channel, message = event_filter.transform(event)
    assert channel == CHANNEL_DRIVER_UPDATES
    assert isinstance(message, DriverUpdateMessage)
    assert message.driver_id == "driver-1"
    assert message.location == (-23.5505, -46.6333)
    assert message.heading is None
    assert message.status == "offline"
    assert message.trip_id is None
    assert message.timestamp == timestamp


def test_transform_rider_profile_to_rider_update(event_filter, timestamp):
    """Rider profile events should transform to RiderUpdateMessage at home location."""
    event = RiderProfileEvent(
        event_type="rider.created",
        rider_id="rider-1",
        timestamp=timestamp,
        first_name="Maria",
        last_name="Santos",
        email="maria@example.com",
        phone="+5511912345678",
        home_location=(-23.5600, -46.6400),
        payment_method_type="credit_card",
        payment_method_masked="****1234",
    )
    channel, message = event_filter.transform(event)
    assert channel == CHANNEL_RIDER_UPDATES
    assert isinstance(message, RiderUpdateMessage)
    assert message.rider_id == "rider-1"
    assert message.location == (-23.5600, -46.6400)
    assert message.trip_id is None
    assert message.timestamp == timestamp
