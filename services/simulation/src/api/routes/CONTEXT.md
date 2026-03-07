# CONTEXT.md — Routes

## Purpose

HTTP route handlers for the simulation's FastAPI application. Organizes endpoints into five distinct functional areas: simulation lifecycle control, autonomous agent management, puppet (manually-controlled) agent control, performance controller proxying, and metrics/infrastructure status aggregation.

## Responsibility Boundaries

- **Owns**: Request validation, state pre-condition enforcement, response shaping, rate limiting per endpoint group
- **Delegates to**: `engine` for simulation state transitions; `agent_factory` for agent spawning; `matching_server` for trip matching and trip state signals; `metrics_collector` for Prometheus data aggregation
- **Does not handle**: Business logic — route handlers are thin adapters that enforce HTTP-layer constraints and delegate all domain logic to injected app-state services

## Key Concepts

**Puppet agents** (`puppet.py`): Manually-controlled agents whose every state transition is triggered via API rather than by the SimPy process loop. Puppet drivers follow a strict sequential workflow: `go-online` → `accept-offer` → `drive-to-pickup` → `arrive-pickup` → `start-trip` → `drive-to-destination` → `complete-trip`. Each endpoint validates the expected prior status and rejects transitions from invalid states. Puppet agents coexist in the same engine as autonomous agents but are identified by `_is_puppet = True`.

**Spawn queue** (`agents.py`): Agent creation does not spawn immediately. `POST /agents/drivers` and `POST /agents/riders` enqueue agents for continuous spawning at a controlled rate (default 2/sec for drivers, 40/sec for riders) to prevent synchronized GPS ping bursts. A `SpawnMode` query parameter switches between `immediate` (agents go active at once) and `scheduled` (agents follow their DNA shift/ride schedule).

**Service registry** (`service_registry.py`): A frozen dataclass catalog declaring every infrastructure service along with its display name, environment scope (`LOCAL`/`PRODUCTION`/`BOTH`), and latency health thresholds. Used by `metrics.py` to determine which services to probe for the infrastructure status card. This is the single authoritative list — adding a new service to the platform requires adding it here.

**Metrics caching** (`metrics.py`): The `/metrics` endpoint aggregates data from Prometheus, cAdvisor, and simulation state. A 500ms module-level cache (`_metrics_cache`) prevents redundant fan-out on rapid polling from the frontend. Machine info (CPU/memory specs) uses a separate 5-minute cache since hardware characteristics are static.

## Non-Obvious Details

- The `simulation.py` router stores `_simulation_start_wall_time` as a module-level global because FastAPI does not provide per-router state. `reset` clears it explicitly. This means wall-clock uptime resets on reset but is unaffected by pause/resume cycles.
- `puppet.py` fare calculation duplicates the formula in `agents.py` (`request_rider_trip`): base fare 5.0 BRL + 2.5 BRL/km × surge. This inline calculation is intentional for puppet routes, since no autonomous rider DNA is driving the logic.
- Teleporting a driver (`PUT /puppet/drivers/{id}/location`) also updates the geospatial H3 index via `matching_server._driver_index.update_driver_location` — but only if the driver is currently `available`. Teleporting an offline or en-route driver updates the agent's `_location` field without updating the spatial index.
- `controller.py` is a pure HTTP proxy to the `performance-controller` service at port 8090. It exists so the control panel can reach the performance controller through a single authenticated API surface rather than exposing the controller port directly.
- `service_registry.py` is not an API route file despite living in this package. It is a data module imported by `metrics.py` and has no FastAPI router.

## Related Modules

- [schemas/api](../../../../../schemas/api/CONTEXT.md) — Shares Agent Architecture and DNA domain (puppet agents)
- [services/control-panel](../../../../control-panel/CONTEXT.md) — Shares Agent Architecture and DNA domain (puppet agents)
- [services/control-panel/src/hooks](../../../../control-panel/src/hooks/CONTEXT.md) — Shares Agent Architecture and DNA domain (puppet agents)
- [services/simulation/src/engine](../../engine/CONTEXT.md) — Shares Agent Architecture and DNA domain (puppet agents)
