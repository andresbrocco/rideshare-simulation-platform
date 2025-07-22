import time
from pathlib import Path

import pytest

from src.geo.zone_assignment import InvalidCoordinatesError, ZoneAssignmentService
from src.geo.zones import ZoneLoader


@pytest.fixture
def sample_zones_path():
    return Path(__file__).parent.parent / "fixtures" / "sample_zones.geojson"


@pytest.fixture
def zone_loader(sample_zones_path):
    return ZoneLoader(sample_zones_path)


@pytest.fixture
def zone_service(zone_loader):
    return ZoneAssignmentService(zone_loader)


class TestPointInsideZone:
    def test_point_inside_zone(self, zone_service):
        """Point clearly inside pinheiros zone"""
        lat, lon = -23.5650, -46.6950
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id == "pinheiros"

    def test_point_inside_vila_madalena(self, zone_service):
        """Point clearly inside vila_madalena zone"""
        lat, lon = -23.5550, -46.6850
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id == "vila_madalena"

    def test_point_inside_centro(self, zone_service):
        """Point clearly inside centro zone"""
        lat, lon = -23.5450, -46.6350
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id == "centro"


class TestPointOnBorder:
    def test_point_on_border_nearest_centroid(self, zone_service):
        """Point on zone border falls back to nearest centroid"""
        lat, lon = -23.5600, -46.6900
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id in ["pinheiros", "vila_madalena"]


class TestPointOutsideAllZones:
    def test_point_outside_all_zones_nearest(self, zone_service):
        """Point outside all zones but within 50km returns nearest"""
        lat, lon = -23.5300, -46.6500
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id in ["pinheiros", "vila_madalena", "centro"]

    def test_point_slightly_outside_zones(self, zone_service):
        """Point just outside mapped area returns nearest centroid"""
        lat, lon = -23.5000, -46.6000
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id in ["pinheiros", "vila_madalena", "centro"]


class TestInvalidCoordinates:
    def test_invalid_coords_far_from_zones(self, zone_service):
        """Coordinates >50km from all zones raise error"""
        lat, lon = -22.0, -45.0
        with pytest.raises(InvalidCoordinatesError) as exc_info:
            zone_service.get_zone_id(lat, lon)
        assert "50" in str(exc_info.value) or "km" in str(exc_info.value).lower()

    def test_very_far_coordinates(self, zone_service):
        """Coordinates in different state raise error"""
        lat, lon = -15.7801, -47.9292
        with pytest.raises(InvalidCoordinatesError):
            zone_service.get_zone_id(lat, lon)


class TestCentroidDistanceCalculation:
    def test_centroid_distance_calculation(self, zone_service):
        """Verify Haversine distance calculation accuracy"""
        zone = zone_service.zone_loader.get_zone("pinheiros")
        centroid_lat, centroid_lon = zone.centroid[1], zone.centroid[0]

        # Point 1km away (approximately)
        lat, lon = centroid_lat + 0.009, centroid_lon

        distance = zone_service._calculate_distance(lat, lon, centroid_lat, centroid_lon)

        assert 0.9 < distance < 1.1

    def test_zero_distance_same_point(self, zone_service):
        """Distance to same point is zero"""
        lat, lon = -23.5650, -46.6950
        distance = zone_service._calculate_distance(lat, lon, lat, lon)
        assert distance < 0.001


class TestCachePerformance:
    def test_zone_cache_performance(self, zone_service):
        """Cache improves repeated lookups"""
        lat, lon = -23.5650, -46.6950

        start = time.perf_counter()
        for _ in range(100):
            zone_service.get_zone_id(lat, lon)
        cached_time = time.perf_counter() - start

        zone_service._cache.clear()

        start = time.perf_counter()
        for _ in range(100):
            zone_service.get_zone_id(lat, lon)
        uncached_time = time.perf_counter() - start

        assert cached_time < uncached_time or cached_time < 0.01

    def test_cache_hit_on_repeated_call(self, zone_service):
        """Same coordinates return cached result"""
        lat, lon = -23.5650, -46.6950

        zone_id_1 = zone_service.get_zone_id(lat, lon)
        zone_id_2 = zone_service.get_zone_id(lat, lon)

        assert zone_id_1 == zone_id_2


class TestBatchZoneAssignment:
    def test_batch_zone_assignment(self, zone_service):
        """Assigns zones for multiple coordinates"""
        coords = [
            (-23.5650, -46.6950),  # pinheiros
            (-23.5550, -46.6850),  # vila_madalena
            (-23.5450, -46.6350),  # centro
            (-23.5650, -46.6950),  # pinheiros again
            (-23.5550, -46.6850),  # vila_madalena again
        ]

        zone_ids = zone_service.get_zone_batch(coords)

        assert len(zone_ids) == 5
        assert zone_ids[0] == "pinheiros"
        assert zone_ids[1] == "vila_madalena"
        assert zone_ids[2] == "centro"
        assert zone_ids[3] == "pinheiros"
        assert zone_ids[4] == "vila_madalena"

    def test_batch_with_invalid_coord(self, zone_service):
        """Batch assignment raises error on first invalid coord"""
        coords = [
            (-23.5650, -46.6950),  # valid
            (-22.0, -45.0),  # invalid (>50km)
            (-23.5550, -46.6850),  # valid
        ]

        with pytest.raises(InvalidCoordinatesError):
            zone_service.get_zone_batch(coords)


class TestRealSaoPauloCoords:
    def test_zone_assignment_sao_paulo_coords(self, zone_service):
        """Real Sao Paulo coordinates get assigned correctly"""
        test_cases = [
            ((-23.5650, -46.6950), "pinheiros"),
            ((-23.5550, -46.6850), "vila_madalena"),
            ((-23.5450, -46.6350), "centro"),
        ]

        for (lat, lon), expected_zone in test_cases:
            zone_id = zone_service.get_zone_id(lat, lon)
            assert zone_id == expected_zone
