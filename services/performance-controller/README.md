# Performance Controller

> Autonomous PID feedback controller that throttles simulation speed to maintain target infrastructure headroom.

## Quick Reference

### Ports

| Port (host) | Port (container) | Description |
|-------------|------------------|-------------|
| 8090 | 8080 | HTTP API (health, status, mode control) |

### Environment Variables

Settings use Pydantic's `env_nested_delimiter="__"` — nested config is set with double-underscore separators (e.g., `CONTROLLER__MAX_SPEED=64`).

| Variable | Default | Description |
|----------|---------|-------------|
| `SIMULATION_API_URL` / `SIMULATION__BASE_URL` | `http://simulation:8000` | Base URL of the simulation REST API |
| `SIMULATION_API_KEY` / `SIMULATION__API_KEY` | _(required)_ | API key sent as `X-API-Key` to the simulation service |
| `PROMETHEUS_URL` / `PROMETHEUS__URL` | `http://prometheus:9090` | Prometheus base URL for headroom queries |
| `CONTROLLER__POLL_INTERVAL` | `5.0` | Seconds between PID control loop iterations |
| `CONTROLLER__MAX_SPEED` | `128.0` | Maximum simulation speed multiplier |
| `CONTROLLER__MIN_SPEED` | `0.5` | Minimum simulation speed multiplier |
| `CONTROLLER__TARGET` | `0.66` | Infrastructure headroom setpoint (0–1) |
| `CONTROLLER__K_UP` | `0.15` | Proportional gain for speed increases (gentle ramp-up) |
| `CONTROLLER__K_DOWN` | `1.5` | Proportional gain for speed decreases (aggressive cut) |
| `CONTROLLER__SMOOTHNESS` | `12.0` | Sigmoid steepness blending k_up and k_down |
| `CONTROLLER__KI` | `0.02` | Integral gain for steady-state error correction |
| `CONTROLLER__KD` | `0.1` | Derivative gain for oscillation dampening |
| `CONTROLLER__INTEGRAL_MAX` | `5.0` | Anti-windup clamp for error integral (error-seconds) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://otel-collector:4317` | OTLP gRPC endpoint for traces and metrics |
| `DEPLOYMENT_ENV` | `local` | Deployment environment tag attached to OTel resource |
| `LOG_FORMAT` | _(empty)_ | Set to `json` for structured JSON log output |
| `API__CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Comma-separated allowed CORS origins |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns mode, speed, headroom, uptime |
| `GET` | `/status` | Detailed controller state including max_speed |
| `PUT` | `/controller/mode` | Enable or disable PID control loop |

**Note:** The controller starts with mode `off`. Speed is only actuated when mode is `on`.

#### Health check

```bash
curl http://localhost:8090/health
```

Example response:

```json
{
  "status": "healthy",
  "mode": "off",
  "current_speed": 128.0,
  "infrastructure_headroom": 0.72,
  "uptime_seconds": 42.3
}
```

#### Detailed status

```bash
curl http://localhost:8090/status
```

#### Enable PID control

```bash
curl -X PUT http://localhost:8090/controller/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "on"}'
```

#### Disable PID control (snaps speed to nearest power-of-two)

```bash
curl -X PUT http://localhost:8090/controller/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "off"}'
```

### Docker Profile

```bash
# Start the performance controller alongside core services
docker compose -f infrastructure/docker/compose.yml \
  --profile core \
  --profile performance \
  up -d performance-controller
```

The service is defined under the `performance` Docker Compose profile and is not started by default.

### Prometheus Metric Dependency

The controller queries a single Prometheus recording rule:

```
rideshare:infrastructure:headroom
```

This recording rule must exist and return a value in `[0, 1]` for the controller to actuate speed. If the metric is absent (e.g., no recording rule configured), the control loop idles silently and logs a debug message each cycle.

### OTel Metrics Exported

Metrics are pushed via OTLP (not scraped). They appear in Prometheus after the OTel Collector forwards them via `remote_write`.

| Metric | Type | Description |
|--------|------|-------------|
| `controller_infrastructure_headroom` | Gauge | Current composite headroom (0–1) |
| `controller_applied_speed` | Gauge | Current simulation speed multiplier applied |
| `controller_mode` | Gauge | 1 = on, 0 = off |
| `controller_error_integral` | Gauge | PID accumulated error (error-seconds) |
| `controller_error_derivative` | Gauge | PID error rate of change |
| `controller_adjustments_total` | Counter | Total speed actuation calls made |

## Common Tasks

### Start the controller and enable PID control

```bash
# 1. Bring up the service
docker compose -f infrastructure/docker/compose.yml --profile core --profile performance up -d performance-controller

# 2. Wait for healthy status
curl http://localhost:8090/health

# 3. Enable PID control
curl -X PUT http://localhost:8090/controller/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "on"}'
```

### Tune the controller for a constrained host

Reduce max speed and make ramp-up more conservative:

```bash
# In docker compose override or environment:
CONTROLLER__MAX_SPEED=32
CONTROLLER__K_UP=0.05
CONTROLLER__TARGET=0.75
```

### Temporarily disable PID without stopping the container

```bash
curl -X PUT http://localhost:8090/controller/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "off"}'
```

When turned off, the controller snaps the simulation speed to the nearest floor power-of-two from `{0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0}`.

### Re-enable PID after external speed change

Switching mode `on` seeds `current_speed` from a live `GET /simulation/status` call, so the controller picks up any externally-applied speed rather than jumping back to its last-known value. PID state (integral, previous error) is also reset to prevent overshoot.

## Troubleshooting

### Controller stays in `off` mode at startup

This is expected. The service starts with mode `off` and does not auto-enable. Send `PUT /controller/mode {"mode": "on"}` once the simulation is running.

### `infrastructure_headroom` is always `0.0` in `/health`

The Prometheus recording rule `rideshare:infrastructure:headroom` is not returning data. Verify:

```bash
# Query Prometheus directly
curl "http://localhost:9090/api/v1/query?query=rideshare:infrastructure:headroom"
```

If the result set is empty, the recording rule may not be loaded or cAdvisor metrics have not arrived yet. Check Prometheus rules at `http://localhost:9090/rules`.

### Speed is not changing even with mode `on`

Check that the simulation API is reachable and the API key is correct:

```bash
curl -H "X-API-Key: <your-key>" http://localhost:8000/simulation/status
```

Actuation failures are logged at `ERROR` level. Also verify `SIMULATION__API_KEY` is set in the container environment.

### Oscillation — speed bounces rapidly

Reduce `CONTROLLER__K_UP` and increase `CONTROLLER__KD`. The default asymmetric gain (`k_up=0.15`, `k_down=1.5`) is already conservative on the ramp-up side. Increasing `smoothness` widens the transition band between the two gains.

### `integral_max` hit — logs show clamped integral

The integral term is saturated. This is normal when headroom is persistently above or below setpoint for a long time (e.g., simulation paused). It self-corrects once the process variable moves toward the target.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context, PID internals, non-obvious behaviors
- [services/simulation](../simulation/README.md) — Simulation service that receives speed actuation calls
- [services/prometheus](../prometheus/README.md) — Prometheus service providing the headroom recording rule
