"""Tests for the centralized distance utility."""

import pytest

from src.geo.distance import (
    _LAT_DEGREES_PER_METER,
    EARTH_RADIUS_M,
    haversine_distance_km,
    haversine_distance_m,
    is_within_proximity,
)


@pytest.mark.unit
class TestHaversineDistanceM:
    """Tests for haversine_distance_m function."""

    def test_same_point_returns_zero(self) -> None:
        """Distance between identical points should be zero."""
        lat, lon = -23.5505, -46.6333  # São Paulo
        distance = haversine_distance_m(lat, lon, lat, lon)
        assert distance == pytest.approx(0.0, abs=0.001)

    def test_known_distance_sao_paulo_to_rio(self) -> None:
        """Test a known distance: São Paulo to Rio de Janeiro ~360km."""
        # São Paulo city center
        sp_lat, sp_lon = -23.5505, -46.6333
        # Rio de Janeiro city center
        rio_lat, rio_lon = -22.9068, -43.1729

        distance_m = haversine_distance_m(sp_lat, sp_lon, rio_lat, rio_lon)
        distance_km = distance_m / 1000

        # Known distance is approximately 360km
        assert 350 <= distance_km <= 370

    def test_short_distance_accuracy(self) -> None:
        """Test accuracy for short distances (~100m)."""
        # Two points approximately 100m apart in São Paulo
        lat1, lon1 = -23.5505, -46.6333
        # Move approximately 100m north (roughly 0.0009 degrees)
        lat2, lon2 = -23.5496, -46.6333

        distance = haversine_distance_m(lat1, lon1, lat2, lon2)

        # Should be approximately 100m (within 10m tolerance)
        assert 90 <= distance <= 110

    def test_symmetry(self) -> None:
        """Distance from A to B should equal distance from B to A."""
        lat1, lon1 = -23.5505, -46.6333
        lat2, lon2 = -23.5600, -46.6400

        distance_ab = haversine_distance_m(lat1, lon1, lat2, lon2)
        distance_ba = haversine_distance_m(lat2, lon2, lat1, lon1)

        assert distance_ab == pytest.approx(distance_ba, rel=1e-9)

    def test_across_equator(self) -> None:
        """Test distance calculation across the equator."""
        # Point north of equator
        lat1, lon1 = 1.0, -46.6333
        # Point south of equator
        lat2, lon2 = -1.0, -46.6333

        distance = haversine_distance_m(lat1, lon1, lat2, lon2)

        # 2 degrees of latitude is approximately 222km
        assert 220_000 <= distance <= 225_000

    def test_across_prime_meridian(self) -> None:
        """Test distance calculation across the prime meridian."""
        lat1, lon1 = 51.5074, -0.5  # West of London
        lat2, lon2 = 51.5074, 0.5  # East of London

        distance = haversine_distance_m(lat1, lon1, lat2, lon2)

        # 1 degree of longitude at ~51°N is approximately 70km
        assert 60_000 <= distance <= 80_000


@pytest.mark.unit
class TestHaversineDistanceKm:
    """Tests for haversine_distance_km function."""

    def test_returns_km_not_m(self) -> None:
        """Verify km function returns 1/1000 of meter function."""
        lat1, lon1 = -23.5505, -46.6333
        lat2, lon2 = -23.5600, -46.6400

        distance_m = haversine_distance_m(lat1, lon1, lat2, lon2)
        distance_km = haversine_distance_km(lat1, lon1, lat2, lon2)

        assert distance_km == pytest.approx(distance_m / 1000, rel=1e-9)

    def test_same_point_returns_zero(self) -> None:
        """Distance between identical points should be zero."""
        lat, lon = -23.5505, -46.6333
        distance = haversine_distance_km(lat, lon, lat, lon)
        assert distance == pytest.approx(0.0, abs=0.000001)


@pytest.mark.unit
class TestIsWithinProximity:
    """Tests for is_within_proximity function."""

    def test_same_point_within_any_threshold(self) -> None:
        """Same point should be within any positive threshold."""
        lat, lon = -23.5505, -46.6333
        assert is_within_proximity(lat, lon, lat, lon, threshold_m=1.0)
        assert is_within_proximity(lat, lon, lat, lon, threshold_m=0.001)

    def test_within_50m_threshold(self) -> None:
        """Test default 50m threshold."""
        lat1, lon1 = -23.5505, -46.6333
        # Move approximately 30m (should be within 50m threshold)
        lat2, lon2 = -23.55023, -46.6333

        assert is_within_proximity(lat1, lon1, lat2, lon2, threshold_m=50.0)

    def test_outside_50m_threshold(self) -> None:
        """Test points outside 50m threshold."""
        lat1, lon1 = -23.5505, -46.6333
        # Move approximately 100m (should be outside 50m threshold)
        lat2, lon2 = -23.5496, -46.6333

        assert not is_within_proximity(lat1, lon1, lat2, lon2, threshold_m=50.0)

    def test_default_threshold_is_50m(self) -> None:
        """Verify default threshold is 50 meters."""
        lat1, lon1 = -23.5505, -46.6333
        # Move approximately 30m
        lat2, lon2 = -23.55023, -46.6333

        # Should work with default threshold
        assert is_within_proximity(lat1, lon1, lat2, lon2)

    def test_boundary_case(self) -> None:
        """Test boundary case at exactly the threshold distance."""
        lat1, lon1 = -23.5505, -46.6333
        # Calculate a point exactly 50m away
        # 50m / 111000m per degree ≈ 0.00045 degrees
        lat2 = lat1 + 0.00045
        lon2 = lon1

        distance = haversine_distance_m(lat1, lon1, lat2, lon2)
        # Should be very close to 50m
        assert 49.9 <= distance <= 50.1

        # At exactly threshold, should be True (<=)
        assert is_within_proximity(lat1, lon1, lat2, lon2, threshold_m=distance)

    def test_realistic_rideshare_scenario(self) -> None:
        """Test realistic scenario: driver arriving at pickup location."""
        # Pickup location
        pickup_lat, pickup_lon = -23.5505, -46.6333

        # Driver 40m away (should trigger arrival)
        driver_nearby_lat = pickup_lat + 0.00036  # ~40m
        driver_nearby_lon = pickup_lon

        # Driver 100m away (should not trigger arrival)
        driver_far_lat = pickup_lat + 0.0009  # ~100m
        driver_far_lon = pickup_lon

        # With 50m threshold
        assert is_within_proximity(
            driver_nearby_lat,
            driver_nearby_lon,
            pickup_lat,
            pickup_lon,
            threshold_m=50.0,
        )
        assert not is_within_proximity(
            driver_far_lat, driver_far_lon, pickup_lat, pickup_lon, threshold_m=50.0
        )


@pytest.mark.unit
class TestBoundingBoxPreCheck:
    """Tests for the bounding box fast-reject in is_within_proximity."""

    def test_lat_degrees_per_meter_constant(self) -> None:
        """Constant should be approximately 9e-6 degrees per meter."""
        assert pytest.approx(1.0 / 111_320, rel=1e-6) == _LAT_DEGREES_PER_METER

    def test_far_away_point_rejected_by_lat_check(self) -> None:
        """A point 10km north should be rejected before Haversine runs."""
        # 10km north, same longitude — well outside the bounding box for 50m threshold
        lat1, lon1 = -23.5505, -46.6333
        lat2 = lat1 + 0.09  # ~10km north
        assert not is_within_proximity(lat1, lon1, lat2, lon1, threshold_m=50.0)

    def test_far_away_point_rejected_by_lon_check(self) -> None:
        """A point 10km east should be rejected before Haversine runs."""
        lat1, lon1 = -23.5505, -46.6333
        lon2 = lon1 + 0.09  # well outside lon threshold for 50m
        assert not is_within_proximity(lat1, lon1, lat1, lon2, threshold_m=50.0)

    def test_nearby_point_reaches_haversine(self) -> None:
        """A point within 30m should pass bounding box and Haversine."""
        lat1, lon1 = -23.5505, -46.6333
        lat2 = lat1 + 0.00027  # ~30m north
        assert is_within_proximity(lat1, lon1, lat2, lon1, threshold_m=50.0)

    def test_no_false_negatives_at_diagonal(self) -> None:
        """Bounding box must not reject points that Haversine would accept.

        A point at (threshold * 0.7, threshold * 0.7) in lat/lon space is
        within the bounding box and within the circular threshold.
        """
        lat1, lon1 = -23.5505, -46.6333
        offset_deg = 30.0 * _LAT_DEGREES_PER_METER  # 30m in each direction
        lat2 = lat1 + offset_deg
        lon2 = lon1 + offset_deg
        # The diagonal Haversine distance is ~42m, inside the 50m threshold
        actual_dist = haversine_distance_m(lat1, lon1, lat2, lon2)
        assert actual_dist < 50.0
        assert is_within_proximity(lat1, lon1, lat2, lon2, threshold_m=50.0)

    def test_conservative_lon_check_no_false_negatives(self) -> None:
        """The conservative lon threshold never produces false negatives.

        At São Paulo's lat (cos≈0.917), the actual lon threshold is ~8.3% narrower
        than lat threshold. Using the same value for both is conservative: some
        candidates that are actually outside the circle pass the lon check but
        are correctly rejected by Haversine.
        """
        lat1, lon1 = -23.5505, -46.6333
        # Point exactly at the bounding-box corner: lon offset == lat_threshold
        lat_threshold = 50.0 * _LAT_DEGREES_PER_METER
        lat2 = lat1
        lon2 = lon1 + lat_threshold * 0.99  # just inside the conservative lon bound

        # This may or may not be within 50m (Haversine decides), but it must not
        # be incorrectly rejected by the bounding box alone.
        result = is_within_proximity(lat1, lon1, lat2, lon2, threshold_m=50.0)
        haversine_result = haversine_distance_m(lat1, lon1, lat2, lon2) <= 50.0
        assert result == haversine_result


@pytest.mark.unit
class TestEarthRadius:
    """Tests for earth radius constant."""

    def test_earth_radius_value(self) -> None:
        """Verify earth radius is correct (6,371 km in meters)."""
        assert EARTH_RADIUS_M == 6_371_000
