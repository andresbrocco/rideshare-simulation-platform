# CONTEXT.md — Hooks

## Purpose

Custom React hooks that encapsulate all data-fetching, real-time state management, and UI interaction logic for the control panel. They act as the boundary between raw API/WebSocket data and the component tree, handling connection lifecycle, performance optimizations, and domain-specific state mutation rules.

## Responsibility Boundaries

- **Owns**: WebSocket connection lifecycle, GPS ping buffering, simulation entity state (drivers, riders, trips, surge), REST polling for metrics and infrastructure, deck.gl layer assembly, puppet agent control API calls
- **Delegates to**: `../layers/agentLayers` and `../layers/zoneLayers` for layer construction; `../contexts/performanceContextDef` for frontend FPS/WS-rate tracking; `../lib/toast` for user feedback
- **Does not handle**: Rendering, API authentication configuration (API key is read from `sessionStorage` at call time), WebSocket URL construction

## Key Concepts

- **Snapshot vs. incremental update**: `useSimulationState` handles two distinct message paths. A `snapshot` message replaces all entity state wholesale (used on connect/reconnect). Subsequent `driver_update`, `rider_update`, `trip_update`, and `surge_update` messages apply targeted mutations to the existing Maps.
- **GPS ping buffering**: High-frequency `gps_ping` messages are coalesced into a 100ms batch (`GPS_BUFFER_INTERVAL_MS`). The buffer key is `entity_type:id`, so only the latest ping per entity is kept. A single `setState` call flushes the whole batch, reducing re-renders by roughly 10x versus immediate updates.
- **Route cache eviction**: When a `trip_update` arrives with status `completed` or `cancelled`, `evictTripFromRouteCache` is called before removing the trip from state. This frees cached OSRM route geometry held in `agentLayers`.
- **Rider `trip_state` guard**: A stale GPS ping arriving after trip completion could set a rider's `trip_state` back to `in_transit`. The flush logic explicitly blocks transitions from `idle` → `in_transit` via GPS ping.
- **Puppet agents**: `useSimulationControl` exposes a second tier of API calls (`/agents/puppet/*`) for manually controlled agents — accept/reject offers, teleport, force timeouts. These are distinct from the bulk spawn endpoints.
- **Performance split**: Backend simulation metrics (`/metrics/performance`) are fetched via `usePerformanceMetrics` at 1Hz. Frontend metrics (WS messages/sec, render FPS) are tracked separately via `PerformanceContext` and accessed through `usePerformanceContext`.
- **Layer ordering**: `useSimulationLayers` pushes deck.gl layers in a deliberate order — zones → heatmap → route trails → agents — so that click-pick priority favors agents (last-pushed = highest pick priority in deck.gl).

## Non-Obvious Details

- `useWebSocket` uses `useLayoutEffect` (not `useEffect`) to update callback refs. This ensures the latest `onMessage` function is in the ref before any queued microtasks fire, preventing stale-closure issues during rapid reconnects.
- `useWebSocket` maintains a client-side event deduplication cache (max 1000 entries, FIFO eviction) keyed on `event_id`. This guards against WebSocket at-least-once re-delivery.
- `useAgentState` suppresses `setLoading(true)` on polling refreshes (only sets loading on the initial load). This prevents the inspector panel from flashing a loading state on every 3-second poll.
- `usePerformanceController` silently returns `null` when the performance controller sidecar is unreachable, rather than surfacing an error. Components should treat `null` as "profile not enabled."
- `useZones` fetches from `/zones.geojson` (a static file served by the frontend build), not from the simulation API. Zone boundary data is load-once, not polled.
- API key is read from `sessionStorage` at the moment each request is made, not stored in hook state. This means the key is always current if the user updates it without unmounting the hook.

## Related Modules

- [schemas/api](../../../../schemas/api/CONTEXT.md) — Shares Agent Architecture and DNA domain (puppet agents)
- [services/control-panel](../../CONTEXT.md) — Shares Agent Architecture and DNA domain (puppet agents)
- [services/control-panel/src](../CONTEXT.md) — Reverse dependency — Provides App (default), theme (PALETTE, UI, OFFLINE, STAGE_RGB, STAGE_CSS, STAGE_HEX, injectCssVars), services/lambda (validateApiKey, triggerDeploy, getSessionStatus, getServiceHealth, etc.) (+2 more)
- [services/control-panel/src/components](../components/CONTEXT.md) — Reverse dependency — Provides Map, ControlPanel, InspectorPopup (+19 more)
- [services/simulation/src/api/routes](../../../simulation/src/api/routes/CONTEXT.md) — Shares Agent Architecture and DNA domain (puppet agents)
- [services/simulation/src/engine](../../../simulation/src/engine/CONTEXT.md) — Shares Agent Architecture and DNA domain (puppet agents)
