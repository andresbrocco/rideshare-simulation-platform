# Performance Controller — CONTEXT.md

## Purpose

Independent sidecar that monitors system saturation via Prometheus recording rules and auto-throttles the simulation speed multiplier to prevent pipeline overload. Supports on/off mode toggling from the control panel.

## Architecture

- **Option B design**: Standalone service that queries Prometheus HTTP API and calls the simulation REST API
- **No direct Kafka dependency**: Reads Kafka lag via kafka-exporter metrics in Prometheus
- **OTel metrics export**: Pushes `controller_*` metrics via OTLP → OTel Collector → Prometheus
- **PID control**: Sigmoid-blended asymmetric P-gain with integral and derivative terms (no discrete thresholds)

## Control Loop

1. **Wait for Prometheus** to be reachable
2. **Poll cycle** (every 5s): Read `rideshare:infrastructure:headroom` from Prometheus → if mode is "on": decide speed → actuate

## Infrastructure Headroom

The composite index is computed by Prometheus recording rules in `services/prometheus/rules/performance.yml`, not by the controller. This means the index is always available in Grafana when the simulation is running, regardless of whether the controller sidecar is deployed.

### Components (each 0-1, higher = healthier)

| Rule | Threshold |
|------|-----------|
| `rideshare:performance:kafka_lag_headroom` | 10,000 messages |
| `rideshare:performance:simpy_queue_headroom` | 500 events |
| `rideshare:performance:cpu_headroom` | 85% |
| `rideshare:performance:memory_headroom` | 85% |
| `rideshare:performance:consumption_ratio` | consumed/produced rate |

Composite: `rideshare:infrastructure:headroom` = min of all components.

## Mode (on/off)

- **off** (default): Controller reads and exposes the infrastructure headroom but does not actuate speed changes. The control panel speed dropdown remains functional.
- **on**: Controller runs decide/actuate logic. The control panel shows auto-managed speed display.

Mode is toggled via `PUT /controller/mode` or the "Auto" toggle in the control panel.

## Throttle Logic

PID controller with asymmetric proportional gain and a target setpoint (default 0.66):

```
error         = infrastructure_headroom - target
integral     += error * dt                              # clamped to [-integral_max, +integral_max]
derivative    = (error - previous_error) / dt           # skipped on first cycle

blend         = 1 / (1 + exp(-smoothness * error))     # sigmoid 0→1
effective_k   = k_down + (k_up - k_down) * blend       # large below target, small above
p_factor      = exp(effective_k * error)                # asymmetric P-term
i_factor      = exp(ki * integral)                      # steady-state correction
d_factor      = exp(kd * derivative)                    # oscillation dampening

factor        = p_factor * i_factor * d_factor
new_speed     = clamp(current_speed * factor, min, max)
```

The P-term sigmoid blends between `k_down` (aggressive cut-down, default 1.5) and `k_up` (gentle ramp-up, default 0.15). The I-term corrects persistent steady-state error. The D-term dampens oscillation. Setting `ki=0` or `kd=0` disables that term, reducing to pure P-control.

## Speed Range

The controller operates across floats in **[0.125, 32.0]** via the continuous proportional formula. Both `CONTROLLER_MIN_SPEED` (default `0.125`) and `CONTROLLER_MAX_SPEED` (default `32`) are configurable via environment variables.

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
| `controller_infrastructure_headroom` | ObservableGauge | performance-engineering.json |
| `controller_applied_speed` | ObservableGauge | performance-engineering.json |
| `controller_adjustments_total` | Counter | performance-engineering.json |
| `controller_mode` | ObservableGauge | performance-engineering.json |
| `controller_error_integral` | ObservableGauge | performance-engineering.json |
| `controller_error_derivative` | ObservableGauge | performance-engineering.json |

## Dependencies

- **Prometheus** (reads recording rules via HTTP API)
- **Simulation API** (writes speed via `PUT /simulation/speed`)
- **OTel Collector** (pushes metrics via OTLP gRPC)
- **Secrets** (`API_KEY` from `/secrets/core.env`)
