import json
from unittest.mock import Mock, call

import pytest
import simpy

from src.matching.offer_timeout import OfferTimeoutManager
from src.trip import Trip, TripState


@pytest.fixture
def env():
    return simpy.Environment()


@pytest.fixture
def mock_kafka_producer():
    return Mock()


@pytest.fixture
def timeout_manager(env, mock_kafka_producer):
    return OfferTimeoutManager(env, mock_kafka_producer, timeout_seconds=15)


@pytest.fixture
def sample_trip():
    return Trip(
        trip_id="trip123",
        rider_id="rider1",
        pickup_location=(-23.550520, -46.633308),
        dropoff_location=(-23.561684, -46.656139),
        pickup_zone_id="zone1",
        dropoff_zone_id="zone2",
        surge_multiplier=1.0,
        fare=15.50,
        state=TripState.OFFER_SENT,
        offer_sequence=1,
    )


def test_offer_timeout_manager_init(env, mock_kafka_producer):
    manager = OfferTimeoutManager(env, mock_kafka_producer, timeout_seconds=15)
    assert manager.timeout_seconds == 15
    assert manager.pending_offers == {}


def test_track_pending_offer(timeout_manager, sample_trip):
    timeout_manager.start_offer_timeout(sample_trip, "driver1", 1)
    assert "trip123" in timeout_manager.pending_offers
    pending = timeout_manager.pending_offers["trip123"]
    assert pending.trip.trip_id == "trip123"
    assert pending.driver_id == "driver1"
    assert pending.offer_sequence == 1
    assert pending.timeout_process is not None


def test_offer_expires_after_timeout(env, mock_kafka_producer, sample_trip):
    manager = OfferTimeoutManager(env, mock_kafka_producer, timeout_seconds=15)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=16)

    mock_kafka_producer.produce.assert_called_once()
    call_args = mock_kafka_producer.produce.call_args
    assert call_args[1]["topic"] == "trips"
    event_data = json.loads(call_args[1]["value"])
    assert event_data["trip_id"] == "trip123"
    assert event_data["driver_id"] == "driver1"
    assert event_data["offer_sequence"] == 1
    assert event_data["event_type"] == "trip.offer_expired"
    assert "trip123" not in manager.pending_offers


def test_offer_accepted_before_timeout(env, mock_kafka_producer, sample_trip):
    manager = OfferTimeoutManager(env, mock_kafka_producer, timeout_seconds=15)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=10)
    manager.clear_offer("trip123", "accepted")
    env.run(until=20)

    mock_kafka_producer.produce.assert_not_called()
    assert "trip123" not in manager.pending_offers


def test_offer_rejected_before_timeout(env, mock_kafka_producer, sample_trip):
    manager = OfferTimeoutManager(env, mock_kafka_producer, timeout_seconds=15)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=5)
    manager.clear_offer("trip123", "rejected")
    env.run(until=20)

    mock_kafka_producer.produce.assert_not_called()
    assert "trip123" not in manager.pending_offers


def test_increment_offer_sequence_on_expire(env, mock_kafka_producer):
    trip = Trip(
        trip_id="trip123",
        rider_id="rider1",
        pickup_location=(-23.550520, -46.633308),
        dropoff_location=(-23.561684, -46.656139),
        pickup_zone_id="zone1",
        dropoff_zone_id="zone2",
        surge_multiplier=1.0,
        fare=15.50,
        state=TripState.OFFER_SENT,
        offer_sequence=1,
    )

    manager = OfferTimeoutManager(env, mock_kafka_producer, timeout_seconds=15)
    manager.start_offer_timeout(trip, "driver1", 1)

    env.run(until=16)

    call_args = json.loads(mock_kafka_producer.produce.call_args[1]["value"])
    assert call_args["offer_sequence"] == 1


def test_concurrent_offer_invalidation(env, mock_kafka_producer, sample_trip):
    manager = OfferTimeoutManager(env, mock_kafka_producer, timeout_seconds=15)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=8)
    manager.invalidate_offer("trip123")
    env.run(until=20)

    mock_kafka_producer.produce.assert_not_called()
    assert "trip123" not in manager.pending_offers


def test_multiple_pending_offers(env, mock_kafka_producer):
    manager = OfferTimeoutManager(env, mock_kafka_producer, timeout_seconds=15)

    trip1 = Trip(
        trip_id="trip1",
        rider_id="rider1",
        pickup_location=(-23.550520, -46.633308),
        dropoff_location=(-23.561684, -46.656139),
        pickup_zone_id="zone1",
        dropoff_zone_id="zone2",
        surge_multiplier=1.0,
        fare=15.50,
        state=TripState.OFFER_SENT,
        offer_sequence=1,
    )
    trip2 = Trip(
        trip_id="trip2",
        rider_id="rider2",
        pickup_location=(-23.550520, -46.633308),
        dropoff_location=(-23.561684, -46.656139),
        pickup_zone_id="zone1",
        dropoff_zone_id="zone2",
        surge_multiplier=1.0,
        fare=15.50,
        state=TripState.OFFER_SENT,
        offer_sequence=1,
    )
    trip3 = Trip(
        trip_id="trip3",
        rider_id="rider3",
        pickup_location=(-23.550520, -46.633308),
        dropoff_location=(-23.561684, -46.656139),
        pickup_zone_id="zone1",
        dropoff_zone_id="zone2",
        surge_multiplier=1.0,
        fare=15.50,
        state=TripState.OFFER_SENT,
        offer_sequence=1,
    )

    manager.start_offer_timeout(trip1, "driver1", 1)
    manager.start_offer_timeout(trip2, "driver2", 1)
    manager.start_offer_timeout(trip3, "driver3", 1)

    assert len(manager.pending_offers) == 3

    env.run(until=16)

    assert len(manager.pending_offers) == 0
    assert mock_kafka_producer.produce.call_count == 3

    trip_ids = {
        json.loads(call[1]["value"])["trip_id"]
        for call in mock_kafka_producer.produce.call_args_list
    }
    assert trip_ids == {"trip1", "trip2", "trip3"}


def test_clear_offer_on_match(env, mock_kafka_producer, sample_trip):
    manager = OfferTimeoutManager(env, mock_kafka_producer, timeout_seconds=15)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=7)
    manager.clear_offer("trip123", "accepted")
    env.run(until=20)

    mock_kafka_producer.produce.assert_not_called()
    assert "trip123" not in manager.pending_offers


def test_simpy_timeout_integration(env, mock_kafka_producer, sample_trip):
    manager = OfferTimeoutManager(env, mock_kafka_producer, timeout_seconds=15)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=14)
    mock_kafka_producer.produce.assert_not_called()

    env.run(until=16)
    mock_kafka_producer.produce.assert_called_once()


def test_expired_offer_emits_event(env, mock_kafka_producer, sample_trip):
    manager = OfferTimeoutManager(env, mock_kafka_producer, timeout_seconds=15)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=16)

    mock_kafka_producer.produce.assert_called_once()
    call_args = mock_kafka_producer.produce.call_args
    assert call_args[1]["topic"] == "trips"

    event_data = json.loads(call_args[1]["value"])
    assert event_data["trip_id"] == "trip123"
    assert event_data["driver_id"] == "driver1"
    assert event_data["offer_sequence"] == 1
    assert event_data["event_type"] == "trip.offer_expired"
    # Timestamp is now ISO 8601 format
    assert "timestamp" in event_data
