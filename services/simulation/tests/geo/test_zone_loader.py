import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.geo.zones import Zone, ZoneLoader


@pytest.fixture
def sample_zones_path():
    return Path(__file__).parent.parent / "fixtures" / "sample_zones.geojson"


@pytest.fixture
def invalid_zones_path():
    return Path(__file__).parent.parent / "fixtures" / "invalid_zones.geojson"


@pytest.mark.unit
class TestZoneModel:
    def test_zone_model_valid(self):
        zone = Zone(
            zone_id="PIN",
            name="PINHEIROS",
            demand_multiplier=1.7,
            surge_sensitivity=0.9,
            geometry=[
                (-46.7000, -23.5600),
                (-46.7000, -23.5700),
                (-46.6900, -23.5700),
                (-46.6900, -23.5600),
                (-46.7000, -23.5600),
            ],
            centroid=(-46.6950, -23.5650),
        )

        assert zone.zone_id == "PIN"
        assert zone.name == "PINHEIROS"
        assert zone.demand_multiplier == 1.7
        assert zone.surge_sensitivity == 0.9
        assert len(zone.geometry) == 5
        assert zone.centroid == (-46.6950, -23.5650)

    def test_zone_demand_multiplier_bounds(self):
        with pytest.raises(ValidationError):
            Zone(
                zone_id="test",
                name="Test",
                demand_multiplier=0.0,
                surge_sensitivity=1.0,
                geometry=[(-46.7, -23.56), (-46.69, -23.56), (-46.7, -23.56)],
                centroid=(-46.695, -23.56),
            )

        with pytest.raises(ValidationError):
            Zone(
                zone_id="test",
                name="Test",
                demand_multiplier=-1.0,
                surge_sensitivity=1.0,
                geometry=[(-46.7, -23.56), (-46.69, -23.56), (-46.7, -23.56)],
                centroid=(-46.695, -23.56),
            )

    def test_zone_surge_sensitivity_bounds(self):
        with pytest.raises(ValidationError):
            Zone(
                zone_id="test",
                name="Test",
                demand_multiplier=1.0,
                surge_sensitivity=-0.1,
                geometry=[(-46.7, -23.56), (-46.69, -23.56), (-46.7, -23.56)],
                centroid=(-46.695, -23.56),
            )

        with pytest.raises(ValidationError):
            Zone(
                zone_id="test",
                name="Test",
                demand_multiplier=1.0,
                surge_sensitivity=2.1,
                geometry=[(-46.7, -23.56), (-46.69, -23.56), (-46.7, -23.56)],
                centroid=(-46.695, -23.56),
            )

        zone = Zone(
            zone_id="test",
            name="Test",
            demand_multiplier=1.0,
            surge_sensitivity=2.0,
            geometry=[(-46.7, -23.56), (-46.69, -23.56), (-46.7, -23.56)],
            centroid=(-46.695, -23.56),
        )
        assert zone.surge_sensitivity == 2.0

    def test_zone_centroid_calculation(self):
        polygon_coords = [
            (-46.7000, -23.5600),
            (-46.7000, -23.5700),
            (-46.6900, -23.5700),
            (-46.6900, -23.5600),
            (-46.7000, -23.5600),
        ]

        expected_lon = sum(coord[0] for coord in polygon_coords) / len(polygon_coords)
        expected_lat = sum(coord[1] for coord in polygon_coords) / len(polygon_coords)

        centroid = ZoneLoader._calculate_centroid(polygon_coords)

        assert abs(centroid[0] - expected_lon) < 0.0001
        assert abs(centroid[1] - expected_lat) < 0.0001


@pytest.mark.unit
class TestGeoJSONParsing:
    def test_geojson_feature_parsing(self):
        feature = {
            "type": "Feature",
            "properties": {
                "zone_id": "PIN",
                "name": "PINHEIROS",
                "demand_multiplier": 1.7,
                "surge_sensitivity": 0.9,
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-46.7000, -23.5600],
                        [-46.7000, -23.5700],
                        [-46.6900, -23.5700],
                        [-46.6900, -23.5600],
                        [-46.7000, -23.5600],
                    ]
                ],
            },
        }

        zone = ZoneLoader._parse_feature(feature)

        assert zone.zone_id == "PIN"
        assert zone.name == "PINHEIROS"
        assert zone.demand_multiplier == 1.7
        assert zone.surge_sensitivity == 0.9
        assert len(zone.geometry) == 5

    def test_invalid_polygon_geometry(self):
        feature = {
            "type": "Feature",
            "properties": {
                "zone_id": "invalid",
                "name": "Invalid",
            },
            "geometry": {
                "type": "Point",
                "coordinates": [-46.7000, -23.5600],
            },
        }

        zone = ZoneLoader._parse_feature(feature)
        assert zone is None


@pytest.mark.unit
class TestZoneLoader:
    def test_zone_loader_loads_file(self, sample_zones_path):
        loader = ZoneLoader(sample_zones_path)
        zones = loader.get_all_zones()

        assert len(zones) == 3
        assert "PIN" in [z.zone_id for z in zones]
        assert "BVI" in [z.zone_id for z in zones]
        assert "SEE" in [z.zone_id for z in zones]

    def test_zone_loader_filters_invalid(self, invalid_zones_path):
        loader = ZoneLoader(invalid_zones_path)
        zones = loader.get_all_zones()

        assert len(zones) == 1
        assert zones[0].zone_id == "valid_zone"

    def test_zone_by_id_lookup(self, sample_zones_path):
        loader = ZoneLoader(sample_zones_path)

        zone = loader.get_zone("PIN")
        assert zone is not None
        assert zone.zone_id == "PIN"
        assert zone.name == "PINHEIROS"

        zone = loader.get_zone("nonexistent")
        assert zone is None

    def test_zone_properties_loaded_correctly(self, sample_zones_path):
        loader = ZoneLoader(sample_zones_path)

        pinheiros = loader.get_zone("PIN")
        assert pinheiros.demand_multiplier == 1.7
        assert pinheiros.surge_sensitivity == 0.9

        bela_vista = loader.get_zone("BVI")
        assert bela_vista.demand_multiplier == 1.3
        assert bela_vista.surge_sensitivity == 1.1

        se = loader.get_zone("SEE")
        assert se.demand_multiplier == 1.3
        assert se.surge_sensitivity == 1.1

    def test_zone_centroid_within_bounds(self, sample_zones_path):
        loader = ZoneLoader(sample_zones_path)

        for zone in loader.get_all_zones():
            lon_values = [coord[0] for coord in zone.geometry]
            lat_values = [coord[1] for coord in zone.geometry]

            min_lon, max_lon = min(lon_values), max(lon_values)
            min_lat, max_lat = min(lat_values), max(lat_values)

            assert min_lon <= zone.centroid[0] <= max_lon
            assert min_lat <= zone.centroid[1] <= max_lat


@pytest.mark.unit
class TestZoneLoaderSpatialIndex:
    def test_polygons_pre_built_for_all_zones(self, sample_zones_path):
        loader = ZoneLoader(sample_zones_path)
        zones = loader.get_all_zones()

        assert len(loader._polygons) == len(zones)
        for zone in zones:
            assert zone.zone_id in loader._polygons

    def test_strtree_is_populated(self, sample_zones_path):
        loader = ZoneLoader(sample_zones_path)

        assert loader._strtree is not None
        assert len(loader._strtree_zone_ids) == len(loader.get_all_zones())

    def test_find_zone_returns_correct_zone(self, sample_zones_path):
        loader = ZoneLoader(sample_zones_path)

        # PIN zone spans lon [-46.72, -46.68], lat [-23.59, -23.55]
        # Center of PIN zone
        result = loader.find_zone_for_location(-23.57, -46.70)
        assert result == "PIN"

    def test_find_zone_for_bela_vista(self, sample_zones_path):
        loader = ZoneLoader(sample_zones_path)

        # BVI zone spans lon [-46.68, -46.64], lat [-23.58, -23.53]
        result = loader.find_zone_for_location(-23.555, -46.66)
        assert result == "BVI"

    def test_centroid_fallback_for_point_outside_all_zones(self, sample_zones_path):
        loader = ZoneLoader(sample_zones_path)

        # A point far from all zones — should fall back to nearest centroid, not None
        result = loader.find_zone_for_location(-24.0, -47.5)
        assert result is not None
        assert result in {z.zone_id for z in loader.get_all_zones()}
