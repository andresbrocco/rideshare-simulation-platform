# OSRM

> Routing engine service providing real-time route calculation, distance estimation, and duration estimation for the Sao Paulo metropolitan area.

## Quick Reference

### Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 5050 | HTTP | OSRM routing API (mapped from container port 5000) |

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OSRM_BASE_URL` | `http://osrm:5000` | Internal service URL used by simulation service |
| `OSRM_THREADS` | `$(nproc)` | Number of threads for routing server (defaults to CPU cores) |
| `OSRM_MAP_SOURCE` | `local` | Build-time arg: `local` (pre-extracted) or `fetch` (download fresh) |

### API Endpoints

| Endpoint | Method | Purpose | Example |
|----------|--------|---------|---------|
| `/route/v1/driving/{coordinates}` | GET | Calculate route between points | See below |
| `/health` | GET | Health check (unofficial) | N/A |

**Example: Calculate route between two points**
```bash
# Format: /route/v1/driving/{lon1},{lat1};{lon2},{lat2}
curl -sf "http://localhost:5050/route/v1/driving/-46.6333,-23.5505;-46.6334,-23.5506"
```

**Response format:**
```json
{
  "routes": [{
    "distance": 123.4,
    "duration": 45.6,
    "geometry": "..."
  }],
  "code": "Ok"
}
```

### Docker Service

**Start OSRM (via core profile):**
```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d osrm
```

**Check health:**
```bash
docker compose -f infrastructure/docker/compose.yml ps osrm
docker compose -f infrastructure/docker/compose.yml logs osrm
```

**Rebuild with fresh map data:**
```bash
# Download latest Geofabrik data (slow, ~10-15 min build)
OSRM_MAP_SOURCE=fetch docker compose -f infrastructure/docker/compose.yml build osrm
```

**Check processing status:**
```bash
docker compose -f infrastructure/docker/compose.yml exec osrm ls -lh /data/
# Look for .osrm-processed marker file
```

### Health Check

The Docker health check validates routing functionality:
```bash
curl -sf "http://localhost:5050/route/v1/driving/-46.6333,-23.5505;-46.6334,-23.5506"
```

- **Interval:** 10s
- **Timeout:** 5s
- **Retries:** 10
- **Start period:** 300s (allows time for initial data processing)

## Common Tasks

### Test routing locally

```bash
# Single route
curl "http://localhost:5050/route/v1/driving/-46.6333,-23.5505;-46.6334,-23.5506?overview=full"

# Multiple waypoints
curl "http://localhost:5050/route/v1/driving/-46.6333,-23.5505;-46.6400,-23.5600;-46.6334,-23.5506"

# Get route geometry for visualization
curl "http://localhost:5050/route/v1/driving/-46.6333,-23.5505;-46.6334,-23.5506?geometries=geojson"
```

### Rebuild processed data

```bash
# Stop service
docker compose -f infrastructure/docker/compose.yml stop osrm

# Remove processed data (forces reprocessing on next start)
docker volume rm rideshare-platform_osrm-data

# Start service (will process OSM data, takes ~3 minutes)
docker compose -f infrastructure/docker/compose.yml --profile core up -d osrm

# Monitor processing
docker compose -f infrastructure/docker/compose.yml logs -f osrm
```

### Update to latest map data

```bash
# Rebuild with fresh download from Geofabrik
OSRM_MAP_SOURCE=fetch docker compose -f infrastructure/docker/compose.yml build --no-cache osrm

# Remove old processed data
docker volume rm rideshare-platform_osrm-data

# Start with new data
docker compose -f infrastructure/docker/compose.yml --profile core up -d osrm
```

### Adjust performance

```bash
# Increase thread count for higher throughput
OSRM_THREADS=8 docker compose -f infrastructure/docker/compose.yml up -d osrm

# Reduce thread count for lower CPU usage
OSRM_THREADS=2 docker compose -f infrastructure/docker/compose.yml up -d osrm
```

## Prerequisites

- **Platform:** linux/amd64 only (uses Rosetta emulation on Apple Silicon)
- **Memory:** 1GB limit configured in compose.yml
- **Disk:** ~200MB for OSM data + ~400MB for processed OSRM files
- **Build requirements (fetch mode only):**
  - osmium-tool (for extracting bounding box)
  - wget (for downloading Geofabrik data)

## Data Processing Pipeline

On first startup, OSRM runs a three-step processing pipeline:

1. **Extract** (`osrm-extract`): Parse OSM PBF into OSRM format (~60s)
2. **Partition** (`osrm-partition`): Create routing hierarchy (~90s)
3. **Customize** (`osrm-customize`): Apply edge weights (~60s)

**Total:** ~3 minutes on first start. Subsequent starts skip this step because processed data persists in the `osrm-data` volume.

### Bounding Box

The Sao Paulo metropolitan area extract covers:
```
West:  -46.9233
South: -24.1044
East:  -46.2664
North: -23.2566
```

This matches the simulation's `zones.geojson` boundaries.

## Troubleshooting

### Service stuck in "starting" state

**Symptom:** `docker compose ps` shows osrm as "starting" for >5 minutes

**Cause:** First-time data processing takes ~3 minutes. Health check has 300s start period.

**Solution:** Check logs to confirm processing is running:
```bash
docker compose -f infrastructure/docker/compose.yml logs osrm
# Look for "Processing OSRM data..." and progress messages
```

### Route requests return empty results

**Symptom:** API returns `"code": "NoRoute"`

**Cause:** Coordinates outside the Sao Paulo bounding box

**Solution:** Verify coordinates are within `-46.9233,-24.1044,-46.2664,-23.2566`

### Slow performance on Apple Silicon

**Symptom:** Routing requests take >100ms

**Cause:** Rosetta emulation for linux/amd64 platform

**Solution:** This is expected behavior. Use fewer threads to reduce CPU overhead:
```bash
OSRM_THREADS=2 docker compose -f infrastructure/docker/compose.yml up -d osrm
```

### Missing processed data after restart

**Symptom:** Service reprocesses data on every restart

**Cause:** `osrm-data` volume was deleted or not mounted

**Solution:** Check volume exists:
```bash
docker volume ls | grep osrm-data
# If missing, recreate:
docker compose -f infrastructure/docker/compose.yml up -d osrm
```

### Build fails with "osmium-tool not found"

**Symptom:** Docker build error when using `OSRM_MAP_SOURCE=fetch`

**Cause:** Build dependency not installed in fetcher stage

**Solution:** This should not happen with the current Dockerfile. Check Docker build logs:
```bash
OSRM_MAP_SOURCE=fetch docker compose -f infrastructure/docker/compose.yml build osrm --progress=plain
```

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context, MLD algorithm details, multi-stage build explanation
- [services/simulation](../simulation/README.md) — Primary consumer of OSRM routing API
