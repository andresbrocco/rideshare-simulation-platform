# CONTEXT.md — Performance Controller

## Purpose

Autonomous feedback control service that throttles the simulation's time-acceleration speed multiplier to keep host infrastructure utilisation at a stable target level. It continuously polls a composite Prometheus recording rule (`rideshare:infrastructure:headroom`), computes a PID-adjusted speed multiplier, and actuates it via the simulation's REST API.

## Responsibility Boundaries

- **Owns**: PID control loop, speed actuation decisions, infrastructure headroom observation, controller mode state (`on`/`off`)
- **Delegates to**: Prometheus (headroom metric via recording rule), Simulation API (`PUT /simulation/speed`, `GET /simulation/status`)
- **Does not handle**: Defining what the headroom metric means (that is Prometheus recording rule territory), agent lifecycle, or data pipeline orchestration

## Key Concepts

- **Infrastructure headroom** (`rideshare:infrastructure:headroom`): A composite Prometheus recording rule value in the range [0, 1] representing available system capacity. The PID controller treats this as its process variable with a default setpoint of `0.66`.
- **Asymmetric PID gain**: The proportional term uses a sigmoid-blended `k_up`/`k_down` pair rather than a single gain constant. `k_down` (default 1.5) is deliberately much larger than `k_up` (default 0.15) so the controller cuts speed aggressively when headroom drops but ramps up gently when headroom recovers. All three PID terms (P, I, D) are applied multiplicatively in the exponential domain (`speed *= exp(k * error)`), not additively.
- **Speed multiplier**: A scalar passed to SimPy's simulation clock that compresses or expands simulated time relative to wall-clock time. The valid range is `[min_speed, max_speed]` (defaults: 0.5–128.0).
- **Manual speed snap**: When the controller is turned `off`, the current continuous speed is snapped to the nearest floor power-of-two from the set `{0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0}` to leave the simulation at a clean, human-readable rate.
- **Anti-windup**: The error integral is clamped to `±integral_max` (default ±5.0 error-seconds) to prevent runaway accumulation when the simulation is paused or headroom is stuck at an extreme.

## Non-Obvious Details

- The controller starts with mode `off` and must be explicitly enabled via `PUT /controller/mode {"mode": "on"}`. It always observes headroom regardless of mode but only actuates speed when mode is `on`.
- When mode is switched `on`, the controller seeds `_current_speed` from a live `GET /simulation/status` call rather than assuming its last-known value, avoiding a sudden jump if the speed was changed externally while the controller was off.
- The PID state (integral, previous error) is zeroed on every `off → on` transition to prevent stale accumulated error from causing an immediate overshoot.
- The API server runs in a daemon thread (not a separate process). The main thread blocks in the control loop. SIGTERM/SIGINT set `_running = False`, which causes `run()` to exit on the next poll tick rather than mid-actuation.
- Metrics are exported via OTLP to the OTel Collector (not via a Prometheus `/metrics` scrape endpoint). Observable Gauges use a `threading.Lock`-protected snapshot dict to hand values across from the control-loop thread to the OTel export thread safely.
- `env_nested_delimiter="__"` in Pydantic settings means nested config is set via double-underscore env vars, e.g., `CONTROLLER__MAX_SPEED=64`.

## Related Modules

- [infrastructure/docker](../../infrastructure/docker/CONTEXT.md) — Reverse dependency — Consumed by this module
