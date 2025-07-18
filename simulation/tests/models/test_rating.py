from uuid import uuid4

import pytest
from pydantic import ValidationError

from simulation.src.rating import Rating


class TestRating:
    def test_rating_valid(self):
        trip_id = uuid4()
        rating = Rating(
            trip_id=trip_id,
            rater_type="rider",
            rater_id="rider_123",
            ratee_type="driver",
            ratee_id="driver_456",
            rating=5,
            timestamp="2025-01-15T10:30:00Z",
        )
        assert rating.rating == 5
        assert rating.trip_id == trip_id
        assert rating.rater_type == "rider"
        assert rating.ratee_type == "driver"

    def test_rating_value_bounds_upper(self):
        with pytest.raises(ValidationError):
            Rating(
                trip_id=uuid4(),
                rater_type="rider",
                rater_id="rider_123",
                ratee_type="driver",
                ratee_id="driver_456",
                rating=6,
                timestamp="2025-01-15T10:30:00Z",
            )

    def test_rating_value_bounds_lower(self):
        with pytest.raises(ValidationError):
            Rating(
                trip_id=uuid4(),
                rater_type="rider",
                rater_id="rider_123",
                ratee_type="driver",
                ratee_id="driver_456",
                rating=0,
                timestamp="2025-01-15T10:30:00Z",
            )

    def test_rating_integer_only(self):
        with pytest.raises(ValidationError):
            Rating(
                trip_id=uuid4(),
                rater_type="rider",
                rater_id="rider_123",
                ratee_type="driver",
                ratee_id="driver_456",
                rating=4.5,
                timestamp="2025-01-15T10:30:00Z",
            )

    def test_rating_rider_to_driver(self):
        rating = Rating(
            trip_id=uuid4(),
            rater_type="rider",
            rater_id="rider_123",
            ratee_type="driver",
            ratee_id="driver_456",
            rating=4,
            timestamp="2025-01-15T10:30:00Z",
        )
        assert rating.rater_type == "rider"
        assert rating.ratee_type == "driver"

    def test_rating_driver_to_rider(self):
        rating = Rating(
            trip_id=uuid4(),
            rater_type="driver",
            rater_id="driver_456",
            ratee_type="rider",
            ratee_id="rider_123",
            rating=3,
            timestamp="2025-01-15T10:30:00Z",
        )
        assert rating.rater_type == "driver"
        assert rating.ratee_type == "rider"
