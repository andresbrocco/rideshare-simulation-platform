# Performance Controller — CONTEXT.md

## Purpose

Independent sidecar that monitors system saturation via Prometheus and auto-throttles the simulation speed multiplier to prevent pipeline overload.

## Architecture

- **Option B design**: Standalone service that queries Prometheus HTTP API and calls the simulation REST API
- **No direct Kafka dependency**: Reads Kafka lag via kafka-exporter metrics in Prometheus
- **OTel metrics export**: Pushes `controller_*` metrics via OTLP → OTel Collector → Prometheus

## Control Loop

1. **Baseline calibration** (30s default): Samples metrics to derive capacity limits
2. **Poll cycle** (every 5s): Query Prometheus → compute performance index → decide speed → actuate

## Performance Index Formula

```
index = min(
    1 - kafka_lag / lag_capacity,
    1 - simpy_queue / queue_capacity,
    1 - cpu_percent / 100,
    1 - memory_percent / 100,
    consumed_rate / produced_rate,
    rtr / baseline_rtr,
)
```

Clamped to [0, 1]. The minimum component is the bottleneck signal.

## Throttle Logic

| Index Range | Action |
|-------------|--------|
| < 0.3 (critical) | Reduce to 25% of current speed |
| < 0.5 (warning) | Reduce to 50% of current speed |
| >= 0.8 for 3 cycles | Double speed (capped at target) |
| 0.5–0.8 | Hold steady, reset healthy counter |

## Spec Deviation

The spec says "min 0.5x" but `PUT /simulation/speed` only accepts `int >= 1`. The effective floor is **1x**. The controller clamps `max(1, computed_speed)`.

## Module Map

| File | Responsibility |
|------|----------------|
| `main.py` | OTel SDK init, signal handling, entrypoint |
| `settings.py` | Pydantic settings (CONTROLLER_, PROMETHEUS_, SIMULATION_) |
| `logging_setup.py` | Structured logging (same pattern as stream-processor) |
| `prometheus_client.py` | HTTP client querying Prometheus instant API |
| `controller.py` | Baseline calibration + control loop + throttle logic |
| `metrics_exporter.py` | OTel observable gauges + counter |
| `api.py` | FastAPI /health and /status endpoints |

## Exported Metrics

| Metric | Type | Dashboard |
|--------|------|-----------|
| `controller_performance_index` | ObservableGauge | performance-engineering.json |
| `controller_target_speed_multiplier` | ObservableGauge | performance-engineering.json |
| `controller_adjustments_total` | Counter | performance-engineering.json |
| `controller_baseline_lag_capacity` | ObservableGauge | status endpoint |
| `controller_baseline_queue_capacity` | ObservableGauge | status endpoint |

## Dependencies

- **Prometheus** (reads metrics via HTTP API)
- **Simulation API** (writes speed via `PUT /simulation/speed`)
- **OTel Collector** (pushes metrics via OTLP gRPC)
- **Secrets** (`API_KEY` from `/secrets/core.env`)
