# OSRM

> Self-contained road-network routing service for the Sao Paulo metropolitan area, providing realistic route geometries for the simulation engine.

## Quick Reference

### Ports

| Host Port | Container Port | Description |
|-----------|---------------|-------------|
| `5050` | `5000` | OSRM HTTP routing API |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OSRM_MAP_SOURCE` | `local` | Build-time arg: `local` (use pre-extracted `.osm.pbf` from Git LFS) or `fetch` (download fresh from Geofabrik at build time) |
| `OSRM_THREADS` | `4` (compose) / `nproc` (container) | Number of routing threads. Override to limit CPU usage in constrained environments. |

### API Endpoints

OSRM exposes the standard [OSRM HTTP API v1](http://project-osrm.org/docs/v5.5.1/api/). The only endpoint actively used by the simulation is the route service:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/route/v1/driving/{lon1},{lat1};{lon2},{lat2}` | Compute driving route between two coordinates |

**Route request example:**

```bash
curl "http://localhost:5050/route/v1/driving/-46.6333,-23.5505;-46.5519,-23.6102?overview=full&geometries=geojson"
```

**Healthcheck probe (also usable manually):**

```bash
curl -sf "http://localhost:5050/route/v1/driving/-46.6333,-23.5505;-46.6334,-23.5506"
```

The simulation service reaches OSRM at `http://osrm:5000` (internal Docker network). The `OSRM_BASE_URL` environment variable on the simulation container is set to this address.

### Docker Service

```yaml
# Profile: core
# Container: rideshare-osrm
# Memory limit: 1g
# Volume: osrm-data:/data  (persists processed routing files across restarts)
```

Start with the rest of the platform:

```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d osrm
```

Build with fresh OSM data from Geofabrik (slow — downloads the full Sudeste region):

```bash
docker compose -f infrastructure/docker/compose.yml build \
  --build-arg OSRM_MAP_SOURCE=fetch osrm
```

## Map Data

| Item | Value |
|------|-------|
| Area | Sao Paulo metropolitan area |
| Bounding box | `-46.9233,-24.1044,-46.2664,-23.2566` (min_lon, min_lat, max_lon, max_lat) |
| Source file | `data/sao-paulo-metro.osm.pbf` (Git LFS) |
| Upstream | [Geofabrik sudeste-latest.osm.pbf](https://download.geofabrik.de/south-america/brazil/sudeste-latest.osm.pbf) |
| Routing algorithm | MLD (Multi-Level Dijkstra) |

## Common Tasks

### Check if OSRM is healthy

```bash
curl -sf "http://localhost:5050/route/v1/driving/-46.6333,-23.5505;-46.6334,-23.5506" \
  && echo "OSRM is up" || echo "OSRM is not responding"
```

### Get a route with full geometry

```bash
curl "http://localhost:5050/route/v1/driving/-46.6333,-23.5505;-46.5519,-23.6102?overview=full&geometries=geojson" \
  | python3 -m json.tool
```

### Force re-processing of OSRM data

The processed routing graph is persisted in the `osrm-data` Docker volume. On container restart, the init script skips re-processing if the `.osrm-processed` marker exists. To force a clean rebuild:

```bash
docker compose -f infrastructure/docker/compose.yml stop osrm
docker volume rm rideshare-platform_osrm-data
docker compose -f infrastructure/docker/compose.yml up -d osrm
```

### Rebuild with fresh OSM data

```bash
# Fetch mode downloads the full Sudeste region (~1 GB) and extracts the Sao Paulo bbox
OSRM_MAP_SOURCE=fetch docker compose -f infrastructure/docker/compose.yml build osrm
docker compose -f infrastructure/docker/compose.yml up -d osrm
```

## Troubleshooting

### Container starts but healthcheck fails for several minutes

This is expected on first startup. The `osrm-init.sh` script runs three processing steps (`osrm-extract` → `osrm-partition` → `osrm-customize`) before the server starts. The healthcheck `start_period` is set to 300 seconds to accommodate this. Monitor progress:

```bash
docker logs -f rideshare-osrm
```

### Build fails at COPY step with a small pointer file

`data/sao-paulo-metro.osm.pbf` is tracked via Git LFS. If you cloned the repo without LFS support, the file is a text pointer stub (~130 bytes) rather than the actual binary. Fix:

```bash
git lfs install
git lfs pull
```

### `apt-get` fails during Docker build

The `osrm/osrm-backend:v5.25.0` base image runs Debian Stretch (EOL). The Dockerfile patches `/etc/apt/sources.list` to use `archive.debian.org`. If this workaround breaks, check whether the archive mirror is still available or pin to a newer OSRM base image.

### Routing returns unexpected results or ignores roads

The bounding box is fixed to the Sao Paulo metro area. Coordinates outside `-46.9233,-24.1044,-46.2664,-23.2566` are not in the road graph and will return no route or an error. This is intentional — the simulation zone is bounded to match this area.

### High CPU usage

OSRM defaults to `nproc` threads inside the container. The compose file caps it at `OSRM_THREADS=4`. To reduce further, set `OSRM_THREADS=2` in your environment before starting:

```bash
OSRM_THREADS=2 docker compose -f infrastructure/docker/compose.yml up -d osrm
```

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context: MLD algorithm, dual-source build, Git LFS details
- [services/simulation/src/geo](../simulation/src/geo/CONTEXT.md) — Consumes OSRM route responses for path geometry
- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Compose service definition
