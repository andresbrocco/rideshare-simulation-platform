# CONTEXT.md — Collectors

## Purpose

Data collection layer for performance testing framework. Gathers container metrics, lifecycle events, and OOM events from Docker infrastructure, abstracting access to cAdvisor API, Docker Inspect, and Simulation API.

## Responsibility Boundaries

- **Owns**: Metric collection from cAdvisor, Docker container state inspection, simulation API interactions, OOM event detection via restart count monitoring
- **Delegates to**: cAdvisor for resource metrics, Docker CLI for container state, Simulation API for control/status
- **Does not handle**: Metric analysis, threshold evaluation, result persistence, test orchestration

## Key Concepts

**OOM Detection Strategy**: Captures baseline restart counts before testing, then polls `docker inspect` to detect count increases. Restart count changes indicate OOM kills more reliably than OOMKilled flag alone.

**cAdvisor Integration**: Mirrors pattern from `services/simulation/src/api/routes/metrics.py`. Memory limit extracted from cAdvisor `spec.memory.limit` field (reflects actual Docker mem_limit). CPU percentage calculated from delta between last two stat samples.

**Immediate Spawn Mode**: All agent spawning uses `mode=immediate` query parameter as specified by test protocol. Ensures deterministic agent counts for reproducible tests.

**Multi-core CPU Handling**: CPU percentages not clamped at 100%. Multi-core containers report usage proportional to effective cores (e.g., Kafka with 1.5 cores reports up to 150%).

## Non-Obvious Details

**Memory Limit Edge Case**: When Docker container has no `mem_limit` set, cAdvisor reports max uint64 or very large value. Treated as "unlimited" (0.0 MB) if exceeds 64 GB threshold.

**Container Name Matching**: cAdvisor response keys vary. Collector checks multiple fields (key substring, aliases array, name field suffix) to reliably find container data.

**Lifecycle Dependencies**: `DockerLifecycleManager.clean_restart()` relies on Docker Compose's `depends_on` health conditions. Services auto-wait for dependencies before starting.

**Spawn Queue Polling**: `wait_for_spawn_complete()` blocks until both driver and rider queues empty. Critical for synchronizing test phases with actual agent instantiation.

## Related Modules

- **[tests/performance/scenarios](../scenarios/CONTEXT.md)** — Scenario implementations that use these collectors to gather performance data during test execution
- **[tests/performance](../CONTEXT.md)** — Parent performance testing framework that coordinates collector usage across scenarios
- **[services/simulation/src/api/routes](../../../services/simulation/src/api/routes/CONTEXT.md)** — Simulation API endpoints that collectors invoke for agent spawning and status queries
