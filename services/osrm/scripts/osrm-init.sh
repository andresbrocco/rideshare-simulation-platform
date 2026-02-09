#!/bin/bash
set -e

# São Paulo metro area extract (pre-built into Docker image)
DATA_FILE="/data/sao-paulo.osrm"
OSM_FILE="/data/sao-paulo.osm.pbf"
PROCESSED_MARKER="/data/.osrm-processed"

if [ -f "$PROCESSED_MARKER" ]; then
    echo "OSRM data already processed, skipping..."
else
    echo "Processing OSRM data for São Paulo metro area..."

    # Clean up any partial data from a previous failed run
    rm -f /data/sao-paulo.osrm*

    if [ ! -f "$OSM_FILE" ]; then
        echo "ERROR: OSM file not found at $OSM_FILE"
        echo "The São Paulo extract should be included in the Docker image."
        exit 1
    fi

    echo "OSM file size: $(ls -lh "$OSM_FILE" | awk '{print $5}')"

    echo "Step 1/3: Extracting..."
    osrm-extract -p /opt/car.lua "$OSM_FILE"

    echo "Step 2/3: Partitioning..."
    osrm-partition /data/sao-paulo.osrm

    echo "Step 3/3: Customizing..."
    osrm-customize /data/sao-paulo.osrm

    touch "$PROCESSED_MARKER"
    echo "OSRM data processing complete!"
fi

echo "Starting OSRM routing server..."
# Use configurable thread count (defaults to all available CPU cores)
THREADS=${OSRM_THREADS:-$(nproc)}
echo "Using $THREADS threads for routing"
exec osrm-routed --algorithm=mld --threads="$THREADS" "$DATA_FILE"
