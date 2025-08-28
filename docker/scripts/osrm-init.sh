#!/bin/bash
set -e

DATA_FILE="/data/sudeste-latest.osrm"
OSM_FILE="/data/sudeste-latest.osm.pbf"

if [ -f "$DATA_FILE" ]; then
    echo "OSRM data already processed, skipping..."
else
    echo "Processing OSRM data for Sao Paulo..."

    if [ ! -f "$OSM_FILE" ]; then
        echo "Downloading Sao Paulo OSM data..."
        wget -O "$OSM_FILE" \
            https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf
    fi

    echo "Step 1/3: Extracting..."
    osrm-extract -p /opt/car.lua "$OSM_FILE"

    echo "Step 2/3: Partitioning..."
    osrm-partition /data/sudeste-latest.osrm

    echo "Step 3/3: Customizing..."
    osrm-customize /data/sudeste-latest.osrm

    echo "OSRM data processing complete!"
fi

echo "Starting OSRM routing server..."
exec osrm-routed --algorithm=mld "$DATA_FILE"
