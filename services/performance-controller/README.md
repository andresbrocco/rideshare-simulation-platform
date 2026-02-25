# Performance Controller

Auto-throttle sidecar that monitors Prometheus metrics and adjusts simulation speed to prevent pipeline saturation.

## Port Reference

| Port | Protocol | Purpose |
|------|----------|---------|
| 8090 | HTTP | Health check and status API |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (status, baseline_complete, current_speed, performance_index, uptime) |
| GET | `/status` | Detailed state (index, speeds, consecutive_healthy, baseline params) |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus base URL |
| `SIMULATION_BASE_URL` | `http://simulation:8000` | Simulation API base URL |
| `SIMULATION_API_KEY` | (from secrets) | API key for simulation auth |
| `CONTROLLER_TARGET_SPEED` | `10` | Desired simulation speed multiplier |
| `CONTROLLER_POLL_INTERVAL_SECONDS` | `5.0` | Seconds between control loop iterations |
| `CONTROLLER_BASELINE_DURATION_SECONDS` | `30.0` | Baseline calibration window |
| `CONTROLLER_CRITICAL_THRESHOLD` | `0.3` | Below this, reduce to 25% speed |
| `CONTROLLER_WARNING_THRESHOLD` | `0.5` | Below this, reduce to 50% speed |
| `CONTROLLER_HEALTHY_THRESHOLD` | `0.8` | Above this for N cycles, increase speed |
| `CONTROLLER_HEALTHY_CYCLES_REQUIRED` | `3` | Consecutive healthy cycles before increase |
| `CONTROLLER_LAG_CAPACITY_MULTIPLIER` | `3.0` | Baseline lag × multiplier = capacity |
| `CONTROLLER_QUEUE_CAPACITY_MULTIPLIER` | `3.0` | Baseline queue × multiplier = capacity |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | OTel Collector gRPC endpoint |
| `LOG_LEVEL` | `INFO` | Logging level |

## Startup

```bash
# Build
docker compose -f infrastructure/docker/compose.yml build performance-controller

# Start with core + monitoring + performance profiles
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile monitoring --profile performance up -d

# Check health
curl http://localhost:8090/health

# Check detailed status
curl http://localhost:8090/status
```

## Depends On

- `secrets-init` (completed) — provides API_KEY
- `simulation` (healthy) — target of speed actuation
- `prometheus` (healthy) — source of saturation metrics
- `otel-collector` (healthy) — sink for controller metrics
