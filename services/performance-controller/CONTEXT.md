# Performance Controller — CONTEXT.md

## Purpose

Independent sidecar that monitors system saturation via Prometheus recording rules and auto-throttles the simulation speed multiplier to prevent pipeline overload. Supports on/off mode toggling from the control panel.

## Architecture

- **Option B design**: Standalone service that queries Prometheus HTTP API and calls the simulation REST API
- **No direct Kafka dependency**: Reads Kafka lag via kafka-exporter metrics in Prometheus
- **OTel metrics export**: Pushes `controller_*` metrics via OTLP → OTel Collector → Prometheus
- **Static thresholds**: Performance index computed by Prometheus recording rules (no baseline calibration)

## Control Loop

1. **Wait for Prometheus** to be reachable
2. **Poll cycle** (every 5s): Read `rideshare:performance:index` from Prometheus → if mode is "on": decide speed → actuate

## Performance Index

The composite index is computed by Prometheus recording rules in `services/prometheus/rules/performance.yml`, not by the controller. This means the index is always available in Grafana when the simulation is running, regardless of whether the controller sidecar is deployed.

### Components (each 0-1, higher = healthier)

| Rule | Threshold |
|------|-----------|
| `rideshare:performance:kafka_lag_headroom` | 10,000 messages |
| `rideshare:performance:simpy_queue_headroom` | 500 events |
| `rideshare:performance:cpu_headroom` | 85% |
| `rideshare:performance:memory_headroom` | 85% |
| `rideshare:performance:consumption_ratio` | consumed/produced rate |

Composite: `rideshare:performance:index` = min of all components.

## Mode (on/off)

- **off** (default): Controller reads and exposes the performance index but does not actuate speed changes. The control panel speed dropdown remains functional.
- **on**: Controller runs decide/actuate logic. The control panel shows auto-managed speed display.

Mode is toggled via `PUT /controller/mode` or the "Auto" toggle in the control panel.

## Throttle Logic

| Index Range | Action |
|-------------|--------|
| < 0.3 (critical) | Reduce to 25% of current speed |
| < 0.5 (warning) | Reduce to 50% of current speed |
| >= 0.8 for 3 cycles | Double speed (capped at target) |
| 0.5–0.8 | Hold steady, reset healthy counter |

## Speed Range

The controller operates across floats in **[0.125, 32.0]** via geometric steps (`CONTROLLER_RAMP_FACTOR`, default 1.5). Both `CONTROLLER_MIN_SPEED` (default `0.125`) and `CONTROLLER_MAX_SPEED` (default `32`) are configurable via environment variables.

## Module Map

| File | Responsibility |
|------|----------------|
| `main.py` | OTel SDK init, signal handling, entrypoint |
| `settings.py` | Pydantic settings (CONTROLLER_, PROMETHEUS_, SIMULATION_) |
| `logging_setup.py` | Structured logging (same pattern as stream-processor) |
| `prometheus_client.py` | HTTP client querying Prometheus instant API |
| `controller.py` | Mode management + control loop + throttle logic |
| `metrics_exporter.py` | OTel observable gauges + counter |
| `api.py` | FastAPI /health, /status, PUT /controller/mode endpoints |

## Exported Metrics

| Metric | Type | Dashboard |
|--------|------|-----------|
| `controller_performance_index` | ObservableGauge | performance-engineering.json |
| `controller_target_speed_multiplier` | ObservableGauge | performance-engineering.json |
| `controller_adjustments_total` | Counter | performance-engineering.json |
| `controller_mode` | ObservableGauge | performance-engineering.json |

## Dependencies

- **Prometheus** (reads recording rules via HTTP API)
- **Simulation API** (writes speed via `PUT /simulation/speed`)
- **OTel Collector** (pushes metrics via OTLP gRPC)
- **Secrets** (`API_KEY` from `/secrets/core.env`)
