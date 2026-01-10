# Build argument to control map source
# - local: Use pre-extracted file from repository (default, fast)
# - fetch: Download fresh from Geofabrik and extract (slow, latest data)
ARG OSRM_MAP_SOURCE=local

#############################################
# Stage: Fetcher (only used when MAP_SOURCE=fetch)
#############################################
FROM ubuntu:22.04 AS fetcher

RUN apt-get update && apt-get install -y \
    osmium-tool \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /extract

# São Paulo Metro bounding box (with padding for routing)
# Covers the full simulation area defined in zones.geojson
# Format: left,bottom,right,top (min_lon,min_lat,max_lon,max_lat)
ENV SAO_PAULO_BBOX="-46.9233,-24.1044,-46.2664,-23.2566"

RUN echo "Downloading Sudeste (SE Brazil) OSM data from Geofabrik..." && \
    wget -q --show-progress -O sudeste.osm.pbf \
        https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf && \
    echo "Extracting São Paulo metropolitan area..." && \
    osmium extract -b ${SAO_PAULO_BBOX} sudeste.osm.pbf -o sao-paulo-metro.osm.pbf --overwrite && \
    rm sudeste.osm.pbf && \
    ls -lh sao-paulo-metro.osm.pbf

#############################################
# Stage: Local (uses pre-extracted file from repo)
#############################################
FROM osrm/osrm-backend:v5.25.0 AS local

WORKDIR /data

# Update apt sources to use archive.debian.org for EOL stretch
RUN sed -i 's/deb.debian.org/archive.debian.org/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/archive.debian.org/g' /etc/apt/sources.list && \
    sed -i '/stretch-updates/d' /etc/apt/sources.list && \
    apt-get update && apt-get install -y wget curl && \
    rm -rf /var/lib/apt/lists/*

# Copy pre-extracted file from repository (Git LFS)
# Bounding box: -46.9233,-24.1044,-46.2664,-23.2566
# Source: Geofabrik sudeste-latest.osm.pbf, extracted with osmium
COPY data/osrm/sao-paulo-metro.osm.pbf /data/sao-paulo.osm.pbf

COPY infrastructure/docker/dockerfiles/scripts/osrm-init.sh /usr/local/bin/osrm-init.sh
RUN chmod +x /usr/local/bin/osrm-init.sh

EXPOSE 5000
CMD ["/usr/local/bin/osrm-init.sh"]

#############################################
# Stage: Fetch (uses freshly downloaded file)
#############################################
FROM osrm/osrm-backend:v5.25.0 AS fetch

WORKDIR /data

# Update apt sources to use archive.debian.org for EOL stretch
RUN sed -i 's/deb.debian.org/archive.debian.org/g' /etc/apt/sources.list && \
    sed -i 's/security.debian.org/archive.debian.org/g' /etc/apt/sources.list && \
    sed -i '/stretch-updates/d' /etc/apt/sources.list && \
    apt-get update && apt-get install -y wget curl && \
    rm -rf /var/lib/apt/lists/*

# Copy freshly downloaded file from fetcher stage
COPY --from=fetcher /extract/sao-paulo-metro.osm.pbf /data/sao-paulo.osm.pbf

COPY infrastructure/docker/dockerfiles/scripts/osrm-init.sh /usr/local/bin/osrm-init.sh
RUN chmod +x /usr/local/bin/osrm-init.sh

EXPOSE 5000
CMD ["/usr/local/bin/osrm-init.sh"]

#############################################
# Final stage: Selected by build arg
#############################################
FROM ${OSRM_MAP_SOURCE} AS final
