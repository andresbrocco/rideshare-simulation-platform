from unittest.mock import Mock

import pytest
import simpy

from src.matching.offer_timeout import OfferTimeoutManager
from src.trip import Trip, TripState


@pytest.fixture
def env():
    return simpy.Environment()


@pytest.fixture
def mock_on_expire():
    return Mock()


@pytest.fixture
def timeout_manager(env, mock_on_expire):
    return OfferTimeoutManager(env, timeout_seconds=10, on_expire=mock_on_expire)


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


@pytest.mark.unit
@pytest.mark.slow
def test_offer_timeout_manager_init(env, mock_on_expire):
    manager = OfferTimeoutManager(env, timeout_seconds=10, on_expire=mock_on_expire)
    assert manager.timeout_seconds == 10
    assert manager.pending_offers == {}


@pytest.mark.unit
@pytest.mark.slow
def test_track_pending_offer(timeout_manager, sample_trip):
    timeout_manager.start_offer_timeout(sample_trip, "driver1", 1)
    assert "trip123" in timeout_manager.pending_offers
    pending = timeout_manager.pending_offers["trip123"]
    assert pending.trip.trip_id == "trip123"
    assert pending.driver_id == "driver1"
    assert pending.offer_sequence == 1
    assert pending.timeout_process is not None


@pytest.mark.unit
@pytest.mark.slow
def test_offer_expires_after_timeout(env, mock_on_expire, sample_trip):
    manager = OfferTimeoutManager(env, timeout_seconds=10, on_expire=mock_on_expire)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=11)

    mock_on_expire.assert_called_once_with("trip123", "driver1")
    assert "trip123" not in manager.pending_offers


@pytest.mark.unit
@pytest.mark.slow
def test_offer_accepted_before_timeout(env, mock_on_expire, sample_trip):
    manager = OfferTimeoutManager(env, timeout_seconds=10, on_expire=mock_on_expire)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=5)
    manager.clear_offer("trip123", "accepted")
    env.run(until=15)

    mock_on_expire.assert_not_called()
    assert "trip123" not in manager.pending_offers


@pytest.mark.unit
@pytest.mark.slow
def test_offer_rejected_before_timeout(env, mock_on_expire, sample_trip):
    manager = OfferTimeoutManager(env, timeout_seconds=10, on_expire=mock_on_expire)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=5)
    manager.clear_offer("trip123", "rejected")
    env.run(until=15)

    mock_on_expire.assert_not_called()
    assert "trip123" not in manager.pending_offers


@pytest.mark.unit
@pytest.mark.slow
def test_increment_offer_sequence_on_expire(env, mock_on_expire):
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

    manager = OfferTimeoutManager(env, timeout_seconds=10, on_expire=mock_on_expire)
    manager.start_offer_timeout(trip, "driver1", 1)

    env.run(until=11)

    mock_on_expire.assert_called_once_with("trip123", "driver1")


@pytest.mark.unit
@pytest.mark.slow
def test_concurrent_offer_invalidation(env, mock_on_expire, sample_trip):
    manager = OfferTimeoutManager(env, timeout_seconds=10, on_expire=mock_on_expire)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=8)
    manager.invalidate_offer("trip123")
    env.run(until=15)

    mock_on_expire.assert_not_called()
    assert "trip123" not in manager.pending_offers


@pytest.mark.unit
@pytest.mark.slow
def test_multiple_pending_offers(env, mock_on_expire):
    manager = OfferTimeoutManager(env, timeout_seconds=10, on_expire=mock_on_expire)

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

    env.run(until=11)

    assert len(manager.pending_offers) == 0
    assert mock_on_expire.call_count == 3

    expired_trip_ids = {c.args[0] for c in mock_on_expire.call_args_list}
    assert expired_trip_ids == {"trip1", "trip2", "trip3"}


@pytest.mark.unit
@pytest.mark.slow
def test_clear_offer_on_match(env, mock_on_expire, sample_trip):
    manager = OfferTimeoutManager(env, timeout_seconds=10, on_expire=mock_on_expire)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=7)
    manager.clear_offer("trip123", "accepted")
    env.run(until=15)

    mock_on_expire.assert_not_called()
    assert "trip123" not in manager.pending_offers


@pytest.mark.unit
@pytest.mark.slow
def test_simpy_timeout_integration(env, mock_on_expire, sample_trip):
    manager = OfferTimeoutManager(env, timeout_seconds=10, on_expire=mock_on_expire)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=9)
    mock_on_expire.assert_not_called()

    env.run(until=11)
    mock_on_expire.assert_called_once()


@pytest.mark.unit
@pytest.mark.slow
def test_expired_offer_calls_on_expire(env, mock_on_expire, sample_trip):
    manager = OfferTimeoutManager(env, timeout_seconds=10, on_expire=mock_on_expire)
    manager.start_offer_timeout(sample_trip, "driver1", 1)

    env.run(until=11)

    mock_on_expire.assert_called_once_with("trip123", "driver1")
