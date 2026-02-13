# CONTEXT.md — Scenarios

## Purpose

Performance test scenario orchestration with resource monitoring

## Responsibility Boundaries

- **Owns**: Scenario execution flow, result aggregation, threshold detection, data export, phase transitions
- **Delegates to**: Collectors for metrics gathering, Simulation API for workload control, Docker for lifecycle management
- **Does not handle**: Metric collection implementation, visualization generation, test framework orchestration

## Key Concepts

**Scenario Protocol**: All scenarios inherit from `BaseScenario` which provides:
- `run()` method returning `ScenarioResult` with metrics and metadata
- `requires_clean_restart` flag controlling Docker cleanup
- Result structure with status (completed/aborted), metrics list, and analysis dict

**Rolling Statistics**: Each scenario maintains rolling windows (configurable size, default 5 samples) to compute:
- Mean/median/max metrics
- Detection of sustained threshold breaches (not just transient spikes)
- Trend analysis for leak detection

**Threshold Triggers**: Scenarios define condition functions that evaluate against rolling stats:
- CPU threshold: sustained >90% for containers with 1.0 core allocation
- Memory threshold: sustained >80% of container memory limit
- OOM trigger: any restart count increase aborts scenario immediately

**Phase Boundaries**: Duration scenario tracks 3 distinct phases:
- Active: spawning and running agents
- Drain: pausing simulation, waiting for in-flight trips
- Cooldown: monitoring resource release after drain

## Non-Obvious Details

Scenarios can skip clean restart (`requires_clean_restart=False`) when continuation from previous state is desired. Only baseline scenario currently uses this to avoid unnecessary restarts.

Threshold detection uses rolling statistics, not instantaneous values, to avoid false positives from transient CPU/memory spikes during agent spawning.

Duration scenario exports phase markers in metrics to enable visualization of phase transitions. Each metric row includes `phase` column for filtering.

Speed scaling scenario calculates `max_reliable_speed` from the last completed step before OOM or threshold breach, not the step that triggered the failure. This ensures derived parameters are safe for subsequent tests.

## Related Modules

- **[tests/performance](../CONTEXT.md)** — Parent framework that orchestrates scenario execution; runner calls scenario.run() sequentially
- **[tests/performance/collectors](../collectors/CONTEXT.md)** — Data collectors used by scenarios to gather metrics during execution
- **[services/simulation/src/api/routes](../../../services/simulation/src/api/routes/CONTEXT.md)** — Simulation API that scenarios control for workload generation
