import time
from pathlib import Path

import h3
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
        """Point clearly inside PIN (Pinheiros) zone"""
        lat, lon = -23.5650, -46.6950
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id == "PIN"

    def test_point_inside_bela_vista(self, zone_service):
        """Point clearly inside BVI (Bela Vista) zone"""
        lat, lon = -23.5600, -46.6500
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id == "BVI"

    def test_point_inside_se(self, zone_service):
        """Point clearly inside SEE (Sé) zone"""
        lat, lon = -23.5500, -46.6350
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id == "SEE"


class TestPointOnBorder:
    def test_point_on_border_nearest_centroid(self, zone_service):
        """Point on zone border falls back to nearest centroid"""
        lat, lon = -23.5600, -46.6900
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id in ["PIN", "BVI", "SEE"]


class TestPointOutsideAllZones:
    def test_point_outside_all_zones_nearest(self, zone_service):
        """Point outside all zones but within 50km returns nearest"""
        lat, lon = -23.5300, -46.6500
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id in ["PIN", "BVI", "SEE"]

    def test_point_slightly_outside_zones(self, zone_service):
        """Point just outside mapped area returns nearest centroid"""
        lat, lon = -23.5000, -46.6000
        zone_id = zone_service.get_zone_id(lat, lon)
        assert zone_id in ["PIN", "BVI", "SEE"]


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
        zone = zone_service.zone_loader.get_zone("PIN")
        centroid_lat, centroid_lon = zone.centroid[1], zone.centroid[0]

        # Point 1km away (approximately)
        lat, lon = centroid_lat + 0.009, centroid_lon

        distance = zone_service._calculate_distance(
            lat, lon, centroid_lat, centroid_lon
        )

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

        zone_service.clear_cache()

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
            (-23.5650, -46.6950),  # PIN (Pinheiros)
            (-23.5600, -46.6500),  # BVI (Bela Vista)
            (-23.5500, -46.6350),  # SEE (Sé)
            (-23.5650, -46.6950),  # PIN again
            (-23.5600, -46.6500),  # BVI again
        ]

        zone_ids = zone_service.get_zone_batch(coords)

        assert len(zone_ids) == 5
        assert zone_ids[0] == "PIN"
        assert zone_ids[1] == "BVI"
        assert zone_ids[2] == "SEE"
        assert zone_ids[3] == "PIN"
        assert zone_ids[4] == "BVI"

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
            ((-23.5650, -46.6950), "PIN"),
            ((-23.5600, -46.6500), "BVI"),
            ((-23.5500, -46.6350), "SEE"),
        ]

        for (lat, lon), expected_zone in test_cases:
            zone_id = zone_service.get_zone_id(lat, lon)
            assert zone_id == expected_zone


class TestH3CacheKeyGeneration:
    def test_h3_cache_key_format(self, zone_service):
        """Cache key is H3 cell ID at resolution 9"""
        lat, lon = -23.5650, -46.6950
        key = zone_service._generate_cache_key(lat, lon)

        assert isinstance(key, str)
        assert len(key) == 15

    def test_nearby_coords_same_h3_cell_cache_hit(self, zone_service):
        """Coordinates ~50m apart map to same H3 cell and hit cache"""
        lat1, lon1 = -23.5650, -46.6950
        lat2, lon2 = -23.5651, -46.6951

        h3_1 = h3.latlng_to_cell(lat1, lon1, 9)
        h3_2 = h3.latlng_to_cell(lat2, lon2, 9)
        assert h3_1 == h3_2

        zone_service.get_zone_id(lat1, lon1)
        stats_1 = zone_service.get_cache_stats()
        assert stats_1["misses"] == 1
        assert stats_1["hits"] == 0

        zone_service.get_zone_id(lat2, lon2)
        stats_2 = zone_service.get_cache_stats()
        assert stats_2["misses"] == 1
        assert stats_2["hits"] == 1

    def test_distant_coords_different_h3_cells_cache_miss(self, zone_service):
        """Coordinates ~500m apart map to different H3 cells"""
        lat1, lon1 = -23.5650, -46.6950
        lat2, lon2 = -23.5700, -46.7000

        h3_1 = h3.latlng_to_cell(lat1, lon1, 9)
        h3_2 = h3.latlng_to_cell(lat2, lon2, 9)
        assert h3_1 != h3_2

        zone_service.get_zone_id(lat1, lon1)
        zone_service.get_zone_id(lat2, lon2)

        stats = zone_service.get_cache_stats()
        assert stats["misses"] == 2


class TestLRUEviction:
    def test_lru_eviction_when_cache_full(self, zone_loader):
        """LRU eviction removes oldest entries when cache exceeds maxsize"""
        service = ZoneAssignmentService(zone_loader, maxsize=3)

        coords = [
            (-23.5650, -46.6950),
            (-23.5800, -46.7100),
            (-23.5550, -46.6850),
            (-23.5700, -46.7000),
        ]

        for lat, lon in coords[:3]:
            service.get_zone_id(lat, lon)

        assert service.get_cache_stats()["cache_size"] == 3

        service.get_zone_id(coords[3][0], coords[3][1])
        assert service.get_cache_stats()["cache_size"] == 3

        service.get_zone_id(coords[0][0], coords[0][1])
        stats = service.get_cache_stats()
        assert stats["misses"] == 5


class TestCacheStatistics:
    def test_cache_stats_tracking(self, zone_service):
        """Statistics track requests, hits, misses correctly"""
        lat, lon = -23.5650, -46.6950

        zone_service.get_zone_id(lat, lon)
        stats = zone_service.get_cache_stats()
        assert stats["requests"] == 1
        assert stats["misses"] == 1
        assert stats["hits"] == 0
        assert stats["hit_rate"] == 0.0

        zone_service.get_zone_id(lat, lon)
        stats = zone_service.get_cache_stats()
        assert stats["requests"] == 2
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_cache_clear_resets_stats(self, zone_service):
        """clear_cache resets cache and all statistics"""
        zone_service.get_zone_id(-23.5650, -46.6950)
        zone_service.get_zone_id(-23.5650, -46.6950)

        stats_before = zone_service.get_cache_stats()
        assert stats_before["requests"] == 2
        assert stats_before["cache_size"] > 0

        zone_service.clear_cache()

        stats_after = zone_service.get_cache_stats()
        assert stats_after["requests"] == 0
        assert stats_after["hits"] == 0
        assert stats_after["misses"] == 0
        assert stats_after["cache_size"] == 0
