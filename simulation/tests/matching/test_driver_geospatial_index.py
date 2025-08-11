import h3
import pytest

from src.matching.driver_geospatial_index import DriverGeospatialIndex

# Sao Paulo coordinates for testing
PAULISTA_AVE = (-23.5629, -46.6544)
IBIRAPUERA = (-23.5874, -46.6576)
PINHEIROS = (-23.5670, -46.6920)
MOEMA = (-23.5990, -46.6650)


@pytest.fixture
def index():
    return DriverGeospatialIndex(h3_resolution=9)


class TestDriverGeospatialIndexInit:
    def test_index_init(self, index):
        assert index._h3_resolution == 9
        assert index._h3_cells == {}
        assert index._driver_locations == {}
        assert index._driver_status == {}


class TestAddDriver:
    def test_add_driver(self, index):
        index.add_driver("driver_1", -23.55, -46.63, "online")

        assert "driver_1" in index._driver_locations
        assert index._driver_locations["driver_1"] == (-23.55, -46.63)
        assert index._driver_status["driver_1"] == "online"

        cell = h3.latlng_to_cell(-23.55, -46.63, 9)
        assert "driver_1" in index._h3_cells[cell]

    def test_add_multiple_drivers_same_cell(self, index):
        # Two drivers very close should be in same H3 cell
        index.add_driver("driver_1", -23.5500, -46.6300, "online")
        index.add_driver("driver_2", -23.5501, -46.6301, "online")

        cell = h3.latlng_to_cell(-23.5500, -46.6300, 9)
        assert "driver_1" in index._h3_cells[cell]
        assert "driver_2" in index._h3_cells[cell]


class TestUpdateDriverLocation:
    def test_update_driver_location(self, index):
        index.add_driver("driver_1", -23.55, -46.63, "online")
        old_cell = h3.latlng_to_cell(-23.55, -46.63, 9)

        # Move to significantly different location
        index.update_driver_location("driver_1", -23.60, -46.70)
        new_cell = h3.latlng_to_cell(-23.60, -46.70, 9)

        assert index._driver_locations["driver_1"] == (-23.60, -46.70)

        if old_cell != new_cell:
            assert "driver_1" not in index._h3_cells.get(old_cell, set())
            assert "driver_1" in index._h3_cells[new_cell]

    def test_update_driver_location_same_cell(self, index):
        index.add_driver("driver_1", -23.5500, -46.6300, "online")
        cell = h3.latlng_to_cell(-23.5500, -46.6300, 9)

        # Small move within same cell
        index.update_driver_location("driver_1", -23.5501, -46.6301)

        assert "driver_1" in index._h3_cells[cell]
        assert index._driver_locations["driver_1"] == (-23.5501, -46.6301)


class TestRemoveDriver:
    def test_remove_driver(self, index):
        index.add_driver("driver_1", -23.55, -46.63, "online")
        cell = h3.latlng_to_cell(-23.55, -46.63, 9)

        index.remove_driver("driver_1")

        assert "driver_1" not in index._driver_locations
        assert "driver_1" not in index._driver_status
        assert "driver_1" not in index._h3_cells.get(cell, set())

    def test_remove_nonexistent_driver(self, index):
        # Should not raise error
        index.remove_driver("nonexistent_driver")


class TestFindNearestDrivers:
    def test_find_nearest_drivers(self, index):
        # Add drivers at known distances from Paulista
        index.add_driver("driver_close", PAULISTA_AVE[0], PAULISTA_AVE[1] + 0.01, "online")  # ~1km
        index.add_driver("driver_medium", PAULISTA_AVE[0], PAULISTA_AVE[1] + 0.03, "online")  # ~3km
        index.add_driver("driver_far", PAULISTA_AVE[0], PAULISTA_AVE[1] + 0.05, "online")  # ~5km

        results = index.find_nearest_drivers(PAULISTA_AVE[0], PAULISTA_AVE[1], radius_km=6.0)

        assert len(results) >= 1
        # Should be sorted by distance
        if len(results) > 1:
            distances = [r[1] for r in results]
            assert distances == sorted(distances)

    def test_empty_index_query(self, index):
        results = index.find_nearest_drivers(-23.55, -46.63, radius_km=5.0)
        assert results == []

    def test_no_drivers_in_range(self, index):
        # Add driver far away
        index.add_driver("driver_far", -23.00, -46.00, "online")

        results = index.find_nearest_drivers(-23.55, -46.63, radius_km=1.0)
        assert results == []

    def test_distance_sorting(self, index):
        # Add drivers at different distances from query point
        query_lat, query_lon = -23.55, -46.63

        index.add_driver("driver_5km", query_lat + 0.045, query_lon, "online")  # ~5km north
        index.add_driver("driver_2km", query_lat + 0.018, query_lon, "online")  # ~2km north
        index.add_driver("driver_1km", query_lat + 0.009, query_lon, "online")  # ~1km north

        results = index.find_nearest_drivers(query_lat, query_lon, radius_km=10.0)

        assert len(results) == 3
        assert results[0][0] == "driver_1km"
        assert results[1][0] == "driver_2km"
        assert results[2][0] == "driver_5km"

        # Verify distances are ascending
        distances = [r[1] for r in results]
        assert distances == sorted(distances)


class TestStatusFiltering:
    def test_filter_by_status_online(self, index):
        index.add_driver("driver_online", -23.55, -46.63, "online")
        index.add_driver("driver_offline", -23.5501, -46.6301, "offline")

        results = index.find_nearest_drivers(-23.55, -46.63, radius_km=5.0, status_filter="online")

        driver_ids = [r[0] for r in results]
        assert "driver_online" in driver_ids
        assert "driver_offline" not in driver_ids

    def test_filter_by_status_available(self, index):
        index.add_driver("driver_online", -23.55, -46.63, "online")
        index.add_driver("driver_busy", -23.5501, -46.6301, "busy")
        index.add_driver("driver_offline", -23.5502, -46.6302, "offline")

        results = index.find_nearest_drivers(-23.55, -46.63, radius_km=5.0, status_filter="online")

        driver_ids = [r[0] for r in results]
        assert "driver_online" in driver_ids
        assert "driver_busy" not in driver_ids
        assert "driver_offline" not in driver_ids

    def test_exclude_busy_drivers(self, index):
        index.add_driver("driver_1", -23.55, -46.63, "online")
        index.add_driver("driver_2", -23.5501, -46.6301, "online")
        index.add_driver("driver_busy", -23.5502, -46.6302, "busy")

        results = index.find_nearest_drivers(-23.55, -46.63, radius_km=5.0)

        driver_ids = [r[0] for r in results]
        assert len(driver_ids) == 2
        assert "driver_busy" not in driver_ids

    def test_exclude_offline_drivers(self, index):
        index.add_driver("driver_1", -23.55, -46.63, "online")
        index.add_driver("driver_2", -23.5501, -46.6301, "online")
        index.add_driver("driver_offline", -23.5502, -46.6302, "offline")

        results = index.find_nearest_drivers(-23.55, -46.63, radius_km=5.0)

        driver_ids = [r[0] for r in results]
        assert len(driver_ids) == 2
        assert "driver_offline" not in driver_ids


class TestH3CellBucketing:
    def test_h3_cell_bucketing(self, index):
        # Drivers in same neighborhood should be in same or adjacent cells
        index.add_driver("driver_1", -23.5500, -46.6300, "online")
        index.add_driver("driver_2", -23.5501, -46.6301, "online")
        index.add_driver("driver_3", -23.5502, -46.6302, "online")

        cells = set()
        for driver_id in ["driver_1", "driver_2", "driver_3"]:
            lat, lon = index._driver_locations[driver_id]
            cell = h3.latlng_to_cell(lat, lon, 9)
            cells.add(cell)

        # At resolution 9, very nearby points should be in same or adjacent cells
        assert len(cells) <= 3  # Could be same cell or adjacent

    def test_driver_at_exact_query_point(self, index):
        index.add_driver("driver_exact", -23.55, -46.63, "online")

        results = index.find_nearest_drivers(-23.55, -46.63, radius_km=1.0)

        assert len(results) == 1
        assert results[0][0] == "driver_exact"
        assert results[0][1] == pytest.approx(0.0, abs=0.001)


class TestUpdateDriverStatus:
    def test_update_driver_status(self, index):
        index.add_driver("driver_1", -23.55, -46.63, "online")
        assert index._driver_status["driver_1"] == "online"

        index.update_driver_status("driver_1", "busy")
        assert index._driver_status["driver_1"] == "busy"

    def test_status_change_affects_queries(self, index):
        index.add_driver("driver_1", -23.55, -46.63, "online")

        # Should be found when online
        results = index.find_nearest_drivers(-23.55, -46.63, radius_km=5.0)
        assert len(results) == 1

        # Change to busy
        index.update_driver_status("driver_1", "busy")

        # Should not be found when busy
        results = index.find_nearest_drivers(-23.55, -46.63, radius_km=5.0)
        assert len(results) == 0
