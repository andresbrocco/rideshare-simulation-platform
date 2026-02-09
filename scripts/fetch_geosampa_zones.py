#!/usr/bin/env python3
"""
Fetch official GeoSampa district boundaries and transform them for the simulation.

This script:
1. Fetches official São Paulo district GeoJSON from GitHub (codigourbano/distritos-sp)
2. Loads subprefecture config for demand/surge parameters
3. Converts MultiPolygon to Polygon (uses largest polygon by area)
4. Transforms properties to match our Zone model
5. Saves the result to services/simulation/data/zones.geojson
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

GEOSAMPA_URL = (
    "https://raw.githubusercontent.com/codigourbano/distritos-sp/master/distritos-sp.geojson"
)
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "services" / "simulation" / "data" / "subprefecture_config.json"
RAW_OUTPUT_PATH = PROJECT_ROOT / "services" / "simulation" / "data" / "distritos-sp-raw.geojson"
SIMPLIFIED_PATH = (
    PROJECT_ROOT / "services" / "simulation" / "data" / "distritos-sp-simplified.geojson"
)
OUTPUT_PATH = PROJECT_ROOT / "services" / "simulation" / "data" / "zones.geojson"


def check_mapshaper_available() -> bool:
    """Check if npx (and thus mapshaper) can be run."""
    if not shutil.which("npx"):
        print("ERROR: npx not found. Please install Node.js:")
        print("  macOS: brew install node")
        print("  Ubuntu: sudo apt install nodejs npm")
        print("  Windows: https://nodejs.org/")
        return False

    try:
        result = subprocess.run(
            ["npx", "--yes", "mapshaper", "--version"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            print(f"ERROR: mapshaper check failed: {result.stderr}")
            return False
        print(f"Using mapshaper {result.stdout.strip()}")
        return True
    except subprocess.TimeoutExpired:
        print("ERROR: mapshaper version check timed out")
        return False
    except FileNotFoundError:
        print("ERROR: npx command not found")
        return False


def run_mapshaper(input_path: Path, output_path: Path) -> None:
    """Run a single mapshaper simplification pass."""
    cmd = [
        "npx",
        "--yes",
        "mapshaper",
        str(input_path),
        "-simplify",
        "visvalingam",
        "1%",
        "-o",
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        raise RuntimeError(f"mapshaper failed:\n{result.stderr}")


def simplify_geojson(input_path: Path, output_path: Path) -> None:
    """Run mapshaper simplification twice with visvalingam 1%."""
    with tempfile.TemporaryDirectory() as tmpdir:
        intermediate = Path(tmpdir) / "intermediate.geojson"

        print("Running first simplification pass (visvalingam 1%)...")
        run_mapshaper(input_path, intermediate)

        print("Running second simplification pass (visvalingam 1%)...")
        run_mapshaper(intermediate, output_path)

    input_size = input_path.stat().st_size
    output_size = output_path.stat().st_size
    reduction = (1 - output_size / input_size) * 100
    print(
        f"Simplification complete: {input_size:,} -> {output_size:,} bytes ({reduction:.1f}% reduction)"
    )


def polygon_area(coords: list) -> float:
    """Calculate approximate polygon area using shoelace formula."""
    if not coords or len(coords) < 3:
        return 0.0
    n = len(coords)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += coords[i][0] * coords[j][1]
        area -= coords[j][0] * coords[i][1]
    return abs(area) / 2.0


def multipolygon_to_polygon(geometry: dict) -> dict:
    """Convert MultiPolygon to Polygon by selecting the largest polygon."""
    if geometry["type"] == "Polygon":
        return geometry

    if geometry["type"] != "MultiPolygon":
        raise ValueError(f"Unsupported geometry type: {geometry['type']}")

    polygons = geometry["coordinates"]
    if len(polygons) == 1:
        return {"type": "Polygon", "coordinates": polygons[0]}

    # Find the largest polygon by area (using outer ring)
    largest_idx = 0
    largest_area = 0.0
    for i, poly in enumerate(polygons):
        outer_ring = poly[0]
        area = polygon_area(outer_ring)
        if area > largest_area:
            largest_area = area
            largest_idx = i

    return {"type": "Polygon", "coordinates": polygons[largest_idx]}


def fetch_geosampa_data() -> dict:
    print(f"Fetching GeoSampa data from {GEOSAMPA_URL}")
    response = httpx.get(GEOSAMPA_URL, timeout=30.0)
    response.raise_for_status()
    return response.json()


def load_subprefecture_config() -> dict:
    print(f"Loading subprefecture config from {CONFIG_PATH}")
    with open(CONFIG_PATH) as f:
        return json.load(f)


def transform_feature(feature: dict, config: dict) -> dict:
    """Transform a GeoSampa feature to our Zone format."""
    props = feature["properties"]

    subpref = props["ds_subpref"]
    subpref_config = config.get(subpref, {})

    if not subpref_config:
        print(f"  WARNING: No config for subprefecture '{subpref}'")
        subpref_config = {"demand_multiplier": 1.0, "surge_sensitivity": 1.2}

    new_properties = {
        "zone_id": props["ds_sigla"],
        "name": props["ds_nome"],
        "subprefecture": subpref,
        "demand_multiplier": subpref_config["demand_multiplier"],
        "surge_sensitivity": subpref_config["surge_sensitivity"],
    }

    # Convert MultiPolygon to Polygon (ZoneLoader only supports Polygon)
    geometry = multipolygon_to_polygon(feature["geometry"])

    return {
        "type": "Feature",
        "properties": new_properties,
        "geometry": geometry,
    }


def validate_output(geojson: dict, config: dict) -> bool:
    """Validate the transformed GeoJSON."""
    features = geojson.get("features", [])

    # Check feature count
    if len(features) != 96:
        print(f"ERROR: Expected 96 features, got {len(features)}")
        return False

    # Check for unique zone_ids
    zone_ids = [f["properties"]["zone_id"] for f in features]
    if len(zone_ids) != len(set(zone_ids)):
        print("ERROR: Duplicate zone_ids found")
        return False

    # Check all subprefectures have config
    subprefs = set(f["properties"]["subprefecture"] for f in features)
    missing = subprefs - set(config.keys())
    if missing:
        print(f"ERROR: Missing config for subprefectures: {missing}")
        return False

    # Check value ranges and geometry types
    for f in features:
        props = f["properties"]
        geom = f["geometry"]

        if geom["type"] != "Polygon":
            print(f"ERROR: Expected Polygon geometry for {props['zone_id']}, got {geom['type']}")
            return False

        if not (0.5 <= props["demand_multiplier"] <= 2.0):
            print(f"ERROR: demand_multiplier out of range for {props['zone_id']}")
            return False
        if not (0.8 <= props["surge_sensitivity"] <= 1.5):
            print(f"ERROR: surge_sensitivity out of range for {props['zone_id']}")
            return False

    return True


def main():
    # Check mapshaper availability
    if not check_mapshaper_available():
        sys.exit(1)

    # Fetch data
    geosampa_data = fetch_geosampa_data()
    features = geosampa_data.get("features", [])
    print(f"Fetched {len(features)} districts from GeoSampa")

    # Save raw data for reference
    print(f"Saving raw data to {RAW_OUTPUT_PATH}")
    with open(RAW_OUTPUT_PATH, "w") as f:
        json.dump(geosampa_data, f, ensure_ascii=False)

    # Simplify geometry with mapshaper (twice for best results)
    simplify_geojson(RAW_OUTPUT_PATH, SIMPLIFIED_PATH)

    # Load simplified data for transformation
    print(f"Loading simplified data from {SIMPLIFIED_PATH}")
    with open(SIMPLIFIED_PATH) as f:
        simplified_data = json.load(f)

    # Load config
    config = load_subprefecture_config()
    print(f"Loaded config for {len(config)} subprefectures")

    # Transform features (using simplified geometries)
    print("Transforming features...")
    transformed_features = [
        transform_feature(f, config) for f in simplified_data.get("features", [])
    ]

    # Build output GeoJSON
    output_geojson = {
        "type": "FeatureCollection",
        "features": transformed_features,
    }

    # Validate
    print("Validating output...")
    if not validate_output(output_geojson, config):
        print("Validation failed!")
        sys.exit(1)

    # Save final output (compact JSON for smaller file size)
    print(f"Saving to {OUTPUT_PATH}")
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output_geojson, f, ensure_ascii=False)

    # Summary with file sizes
    raw_size = RAW_OUTPUT_PATH.stat().st_size
    simplified_size = SIMPLIFIED_PATH.stat().st_size
    final_size = OUTPUT_PATH.stat().st_size

    print("\nTransformation complete!")
    print(f"  Raw GeoJSON: {raw_size:,} bytes")
    print(f"  Simplified GeoJSON: {simplified_size:,} bytes")
    print(f"  Final zones.geojson: {final_size:,} bytes")
    print(f"  Total zones: {len(transformed_features)}")
    print(
        f"  Subprefectures: {len(set(f['properties']['subprefecture'] for f in transformed_features))}"
    )

    # Show sample
    sample = transformed_features[0]["properties"]
    print("\nSample zone:")
    print(f"  zone_id: {sample['zone_id']}")
    print(f"  name: {sample['name']}")
    print(f"  subprefecture: {sample['subprefecture']}")
    print(f"  demand_multiplier: {sample['demand_multiplier']}")
    print(f"  surge_sensitivity: {sample['surge_sensitivity']}")


if __name__ == "__main__":
    main()
