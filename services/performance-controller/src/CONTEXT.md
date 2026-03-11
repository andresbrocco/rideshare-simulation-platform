# CONTEXT.md — performance-controller/src

## Purpose

Implementation of an autonomous closed-loop PID controller that reads a composite infrastructure headroom metric from Prometheus and actuates the simulation's speed multiplier via REST API. The goal is to keep the platform running as fast as possible without exhausting host resources.

## Responsibility Boundaries

- **Owns**: PID control algorithm, speed actuation decisions, controller lifecycle (on/off mode), OTel metric emission, HTTP API for health and mode toggling
- **Delegates to**: `PrometheusClient` for headroom reads, simulation REST API (`PUT /simulation/speed`) for actuation
- **Does not handle**: Computing the headroom metric itself (that lives in Prometheus recording rules), simulation business logic, agent state

## Key Concepts

- **Infrastructure headroom** (`rideshare:infrastructure:headroom`): A composite 0–1 Prometheus recording rule value representing available capacity. The controller targets a setpoint (`CONTROLLER_TARGET`, default 0.66). Values below target mean the system is over-loaded; values above mean headroom exists to run faster.
- **Asymmetric PID gains**: `k_down` (default 1.5) is intentionally much larger than `k_up` (default 0.15). The P-term uses a sigmoid-blended gain (`smoothness=12`) so the controller cuts speed aggressively when overloaded but ramps back up gently. The validator enforces `k_down > k_up`.
- **Multiplicative PID**: The three terms (P, I, D) are applied as multiplicative exponential factors (`exp(k * error)`) on the current speed rather than additive corrections. This avoids negative speeds and gives natural proportional scaling.
- **Anti-windup**: The integral accumulator is clamped to `±integral_max` (default 5.0 error-seconds) to prevent runaway during sustained saturation.
- **Valid manual speeds**: When auto-mode is disabled, speed is snapped to floor-power-of-two values `[0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0]` so the simulation always lands on a clean discrete multiplier.
- **Mode seeding**: When switching from `off` → `on`, the controller fetches the simulation's live speed via `GET /simulation/status` to seed its internal `_current_speed`, avoiding a large initial jump.

## Non-Obvious Details

- The control loop runs on the **main thread** (blocking `run()`) while the FastAPI server runs on a **daemon thread**. Mode changes from the API are therefore cross-thread writes to `_mode`. No explicit lock guards `_mode` — this is safe only because Python's GIL makes single attribute assignments atomic.
- OTel metrics use **observable gauges backed by a thread-safe snapshot dict** (`_snapshot_lock`). The OTel SDK polls callbacks on its own export thread, so raw access to controller state from those callbacks is not safe — hence the snapshot pattern in `metrics_exporter.py`.
- The `controller_mode` gauge is exported as a float (`0.0` / `1.0`) rather than a boolean to satisfy OTel's numeric metric type.
- `NaN` and `Inf` values returned by Prometheus are explicitly treated as missing (`None`) to avoid propagating them into the PID calculation.
- The Prometheus recording rule name is `rideshare:infrastructure:headroom` — if this rule is absent or stale, the controller skips the cycle entirely rather than acting on a zero or default value.
- Settings do **not** use a singleton (`get_settings()` constructs a fresh `Settings()` on each call). This differs from the simulation service's pattern.

## Related Modules

- [services/grafana/dashboards/performance](../../grafana/dashboards/performance/CONTEXT.md) — Shares PID Control & Adaptive Systems domain (infrastructure headroom)
- [services/grafana/dashboards/performance](../../grafana/dashboards/performance/CONTEXT.md) — Shares Performance & Scalability domain (infrastructure headroom)
- [services/performance-controller](../CONTEXT.md) — Shares PID Control & Adaptive Systems domain (anti-windup, infrastructure headroom)
- [services/performance-controller](../CONTEXT.md) — Shares Performance & Scalability domain (infrastructure headroom)
