# CONTEXT.md — schemas/api

## Purpose

Canonical OpenAPI 3.1.0 specification for the Rideshare Simulation Control Panel REST API. This file is the machine-readable contract between the simulation service and its consumers (control panel frontend, integration tests, external tooling). It is generated from the FastAPI application in `services/simulation/src/api`.

## Responsibility Boundaries

- **Owns**: The authoritative API surface definition — endpoints, request/response schemas, authentication requirements, and HTTP semantics
- **Delegates to**: `services/simulation/src/api` for the actual implementation; `services/control-panel` for the client-side usage
- **Does not handle**: Kafka event schemas (see `schemas/kafka`), lakehouse table schemas (see `schemas/lakehouse`), or WebSocket message formats

## Key Concepts

- **Autonomous agents**: Drivers and riders spawned in bulk via `POST /agents/drivers` and `POST /agents/riders`. These agents act independently according to their DNA behavioral parameters and simulation state.
- **Puppet agents**: A separate agent type (`/agents/puppet/...` endpoints) that starts in `offline` status and takes no autonomous actions. All state transitions are externally triggered via API, making them suitable for deterministic testing of matching logic, geospatial behavior, and timeout scenarios.
- **SpawnMode**: Controls whether agents go active immediately (`immediate`) or follow their DNA schedule (`scheduled`). Default differs by agent type — drivers default to `immediate`, riders default to `scheduled`.
- **Rate-throttled spawning**: Agents are not spawned all at once; drivers spawn at ~2/sec and riders at ~40/sec to prevent synchronized GPS ping bursts. Use `GET /agents/spawn-status` to poll the queue.
- **Two-phase pause**: `POST /simulation/pause` initiates RUNNING → DRAINING → PAUSED; it does not pause immediately. The simulation drains in-flight events before fully pausing.
- **API tag groups**: Routes are organized into four tags — `simulation` (lifecycle control), `agents` (autonomous agent management and inspection), `puppet` (externally-controlled agent operations), and `metrics` (real-time aggregate counters).

## Non-Obvious Details

- This file is generated output — edits are overwritten when the simulation service regenerates its spec. The source of truth is `services/simulation/src/api`.
- All endpoints require `X-API-Key` in the request header. There is no unauthenticated surface.
- Puppet agent endpoints include test-specific actions not available on autonomous agents: teleport (`PUT .../location`), force offer timeout, force patience timeout, and manual rating override.
- The `drive-to-pickup` and `drive-on-trip` puppet endpoints are asynchronous — they return immediately and the driver moves in the background via OSRM routing. Progress must be monitored via WebSocket or the agent state endpoint.
- Speed multiplier is constrained to the range 0.5–128 (enforced at the API layer via `SpeedChangeRequest`).

## Related Modules

- [services/control-panel](../../services/control-panel/CONTEXT.md) — Shares Agent Behavior & DNA domain (puppet agents)
- [services/control-panel/src/hooks](../../services/control-panel/src/hooks/CONTEXT.md) — Shares Agent Behavior & DNA domain (puppet agents)
- [services/simulation/tests/engine](../../services/simulation/tests/engine/CONTEXT.md) — Shares SimPy Simulation Engine domain (two-phase pause)
- [services/simulation/tests/engine](../../services/simulation/tests/engine/CONTEXT.md) — Shares Unified Process & Time Management domain (two-phase pause)
