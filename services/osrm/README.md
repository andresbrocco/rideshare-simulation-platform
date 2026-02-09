# OSRM Routing Engine

OSRM v5.25.0 routing service for Sao Paulo metropolitan area.

## Purpose

This directory contains the OSRM service configuration:
- `Dockerfile` - Multi-stage build with local/fetch map modes
- `scripts/osrm-init.sh` - Data processing and server startup script
- `data/sao-paulo-metro.osm.pbf` - Pre-extracted Sao Paulo metro OpenStreetMap data

## Configuration

| Setting | Value |
|---------|-------|
| Image | `osrm/osrm-backend:v5.25.0` (custom Dockerfile) |
| Port | `5050` (mapped to container port `5000`) |
| Platform | `linux/amd64` only |
| Algorithm | Multi-Level Dijkstra (MLD) |
| Volume | `osrm-data` (persists processed routing data) |

### Build Modes

| Mode | Build Arg | Description |
|------|-----------|-------------|
| `local` (default) | `OSRM_MAP_SOURCE=local` | Uses pre-extracted `data/sao-paulo-metro.osm.pbf` — fast, reproducible |
| `fetch` | `OSRM_MAP_SOURCE=fetch` | Downloads latest data from Geofabrik — slow, latest map data |

## Usage

### Start OSRM

```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d osrm
```

### Build with Custom Map Source

```bash
docker compose -f infrastructure/docker/compose.yml --profile core build osrm
# Or with fetch mode:
docker compose -f infrastructure/docker/compose.yml --profile core build --build-arg OSRM_MAP_SOURCE=fetch osrm
```

### Health Check

```bash
curl -s "http://localhost:5050/route/v1/driving/-46.6333,-23.5505;-46.6334,-23.5506"
```

### Route Query

```bash
curl "http://localhost:5050/route/v1/driving/-46.6388,-23.5489;-46.6566,-23.5613?overview=full&geometries=geojson"
```

### View Logs

```bash
docker compose -f infrastructure/docker/compose.yml --profile core logs -f osrm
```

## Troubleshooting

**First startup takes ~3 minutes**: OSRM must run `osrm-extract`, `osrm-partition`, and `osrm-customize` on the OSM data. Subsequent starts are fast because processed data is persisted in the `osrm-data` volume.

**Routes return errors for coordinates outside Sao Paulo**: The map data only covers the Sao Paulo metropolitan bounding box (`-46.9233,-24.1044,-46.2664,-23.2566`). Coordinates outside this area are not routable.

**Slow performance on Apple Silicon**: OSRM runs under `linux/amd64` emulation via Rosetta. This is expected behavior.

**Data volume needs rebuilding**: If the OSM data changes, remove the volume to force reprocessing:
```bash
docker volume rm rideshare-simulation-platform_osrm-data
```

## References

- [OSRM HTTP API](http://project-osrm.org/docs/v5.24.0/api/)
- [OSRM Backend Docker](https://hub.docker.com/r/osrm/osrm-backend)
- [Geofabrik Downloads](https://download.geofabrik.de/south-america/brazil.html)
