# CONTEXT.md — Scenarios

## Purpose

Implements the individual performance test scenarios that exercise the rideshare simulation platform under controlled load. Each scenario orchestrates the full lifecycle of a test run: environment setup, workload execution, metric sampling, and threshold-based termination.

## Responsibility Boundaries

- **Owns**: Scenario lifecycle protocol (setup → execute → teardown), workload generation via the simulation API (start, set-speed, queue agents, pause, stop, reset), per-scenario threshold logic, and phase-aware sample annotation
- **Delegates to**: `collectors/` for raw metric acquisition (Prometheus, Docker lifecycle, OOM detection, simulation API); `analysis/` for post-run statistical computation (baseline calibration, slopes)
- **Does not handle**: Raw data collection mechanics, result persistence/reporting, or cross-scenario orchestration (that lives in the parent `tests/performance/` runner)

## Key Concepts

**BaseScenario**: Abstract class that provides the `setup → execute → teardown` protocol. `setup()` performs a clean Docker restart (down -v, up -d) unless `requires_clean_restart` returns `False`. `execute()` is a generator that yields progress dicts, allowing the runner to observe phases without coupling. `run()` wraps all three phases and produces a `ScenarioResult`.

**RTR (Real-Time Ratio)**: The primary stop signal across all load scenarios. RTR measures how closely simulation time tracks wall-clock time — a value near 1.0 means the simulation is keeping up; collapse below `stress_rtr_collapse_threshold` means the engine is frozen under load. RTR is tracked via a rolling window to avoid false triggers from transient spikes.

**Rolling window threshold**: `RollingStats` (deque with `maxlen`) and `ContainerRollingStats` (per-container memory + CPU) smooth noisy metrics. Window size derives from `stress_rolling_window_seconds / interval_seconds`. Threshold evaluation happens against the rolling average, not instantaneous values.

**BaselineCalibration**: Computed by `BaselineScenario` and passed into subsequent scenarios. It sets dynamic RTR and health-latency thresholds relative to observed idle behavior, replacing fixed config values. `baseline_rtr_source` tracks whether the threshold came from live calibration or config fallback.

**PeakTracker**: Tracks running maximums (Kafka consumer lag, SimPy event queue depth, global CPU sum, worst-container memory %) across all samples. Used to build `failure_snapshot` — the saturation point captured when a threshold triggers — which feeds Prometheus alerting rule divisors.

**DurationLeakScenario phases**: Three sequential phases annotated by sample-count boundaries (not timestamps), since `_get_phase_samples` slices `self._samples` by accumulated counts: `active` (agents running), `drain` (pause called, wait for PAUSED state), `cooldown` (system idle post-drain). Memory slope (MB/min) during `active` and delta vs cooldown end detect persistent leaks.

## Non-Obvious Details

- `StressTestScenario.requires_clean_restart` returns `False` — it intentionally reuses the environment left by `BaselineScenario` (which ran with 0 agents) to avoid an extra cold-start cost. The runner must execute baseline first.
- Agent counts are always split 50/50 between drivers and riders and must be even; the API caps driver batch sizes at 100 and rider batch sizes at 2000, so large counts are automatically chunked.
- The USL saturation knee stop (`_check_saturation_stop`) is present but permanently disabled — it always returns `None`. The only active load-based stop is RTR collapse.
- `SpeedScalingScenario` doubles the multiplier each step (2x → 4x → 8x … up to `max_multiplier`) with a full simulation reset between steps. The agent count stays fixed across steps to isolate speed as the independent variable.
- `DurationLeakScenario` receives `speed_multiplier` as a constructor argument (expected to come from the speed scaling test result) rather than discovering it from config, coupling the two scenarios at the runner level.
- OOM detection and container liveness checks are wired into every `_collect_sample` call in the base class and will set `self._aborted = True`, breaking out of all scenario loops regardless of which scenario is running.

## Related Modules

- [tests](../../CONTEXT.md) — Shares Performance and Load Testing domain (basescenario)
- [tests/performance](../CONTEXT.md) — Shares Observability and Metrics domain (rtr (real-time ratio))
- [tests/performance/analysis](../analysis/CONTEXT.md) — Dependency — Post-processing pipeline that computes statistics, derives dynamic thresholds, g...
- [tests/performance/collectors](../collectors/CONTEXT.md) — Dependency — Data collection adapters for performance test scenarios — container resource met...
