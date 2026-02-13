# CONTEXT.md — API Routes

## Purpose

FastAPI route handlers that translate REST/WebSocket requests into simulation engine commands and queries. This layer serves as the HTTP interface for the control panel and external integrations.

## Responsibility Boundaries

- **Owns**: HTTP request validation, response formatting, authentication enforcement, rate limiting
- **Delegates to**: Simulation engine for state management, matching server for trip coordination, agent factory for spawning
- **Does not handle**: Business logic (in engine/matching/agents), event publishing (in Kafka/Redis clients), state persistence (in engine/database)

## Key Concepts

**Route Modules**: Three exported route groups (plus one internal module) organized by concern:
- `simulation.py` - Lifecycle control (start/pause/resume/stop/reset), speed adjustment, status queries
- `agents.py` - Agent creation, state inspection, control commands for autonomous agents
- `puppet.py` - Manual control API for testing (puppet drivers/riders with step-by-step control)
- `metrics.py` - Real-time metrics aggregation (overview, zones, trips, drivers, riders, performance, infrastructure)

**Dependency Injection Pattern**: All routes use FastAPI's `Depends()` to access app state:
- `EngineDep` - Simulation engine instance
- `DriverRegistryDep` - Driver location/status index
- `MatchingServerDep` - Trip matching and coordination
- `AgentFactoryDep` - Agent spawning with queuing

**Spawn Queuing**: Agent creation uses rate-limited queuing to prevent synchronized GPS ping bursts (drivers: 2/sec, riders: 40/sec). Clients poll `/agents/spawn-status` to monitor progress.

**Two-Phase Pause**: The `/simulation/pause` endpoint initiates draining of in-flight trips before checkpointing, ensuring clean state recovery.

## Non-Obvious Details

**Metrics Caching**: The metrics module caches responses for 500ms (`CACHE_TTL`) to reduce computation overhead from high-frequency polling (120 requests/minute limit).

**Rider State Derivation**: Rider metrics are computed from trip states rather than rider agent status, because matching-phase states (REQUESTED, OFFER_SENT, MATCHED) are ephemeral and transition too quickly to observe. Riders are counted as "offline" during matching.

**Stream Processor Integration**: The `/performance` endpoint attempts to fetch metrics from the stream processor service but gracefully degrades if unavailable (returns `None` for `stream_processor` field).

**Infrastructure Health Checks**: The `/infrastructure` endpoint combines health status checks with cAdvisor container metrics. Containers without health endpoints default to `(HEALTHY, None, "No health endpoint")` and rely on cAdvisor presence detection.

**Puppet Agent Testing**: The `puppet.py` routes provide manual control over agent lifecycle for integration testing. Puppet agents emit GPS pings but take no autonomous actions—all state transitions must be triggered via API.

**Global State**: `_simulation_start_wall_time` in `simulation.py` tracks uptime for status responses. Reset during `/simulation/reset`.

## Related Modules

- **[src/engine](../../engine/CONTEXT.md)** — Simulation engine that routes invoke via ThreadCoordinator for thread-safe command execution
- **[src/matching](../../matching/CONTEXT.md)** — Matching server accessed by routes for trip coordination and driver registry queries
- **[src/agents](../../agents/CONTEXT.md)** — Agent factory and DNA generators used by agent creation endpoints
- **[schemas/api](../../../../../schemas/api/CONTEXT.md)** — OpenAPI spec generated from these routes; defines request/response contracts
- **[services/frontend/src/components/inspector](../../../../frontend/src/components/inspector/CONTEXT.md)** — Frontend inspector components that invoke puppet control endpoints
