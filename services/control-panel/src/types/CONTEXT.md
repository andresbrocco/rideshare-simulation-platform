# CONTEXT.md — Types

## Purpose

Central TypeScript type definitions for the control panel frontend, covering the full surface of the simulation domain: agent state, WebSocket message contracts, map layer visibility, REST API shapes, and system metrics.

## Responsibility Boundaries

- **Owns**: All shared TypeScript interfaces and type aliases used across components, hooks, layers, and services
- **Delegates to**: Nothing — these are pure type declarations with no runtime logic except `DEFAULT_VISIBILITY`
- **Does not handle**: Runtime validation, data transformation, or API communication

## Key Concepts

**Two-tier rider state model**: `Rider.status` is a coarse 4-value enum (`idle | requesting | awaiting_pickup | on_trip`) used for map rendering. `Rider.trip_state` (typed as `TripStateValue`) is a finer 11-value enum that mirrors the backend state machine and is used for detailed inspection and GPS ping classification. These are not interchangeable.

**DNA vs Statistics vs State**: Each agent type has three distinct inspection shapes. `DriverDNA`/`RiderDNA` are frozen behavioral parameters (personality traits, home location, shift preference). `DriverStatistics`/`RiderStatistics` are cumulative counters. `DriverState`/`RiderState` compose all three alongside real-time operational fields (`active_trip`, `pending_offer`, `next_action`).

**`api.ts` vs `api.generated.ts`**: `api.ts` is hand-maintained and holds the runtime domain model (entity shapes, metric aggregates, health responses). `api.generated.ts` is auto-generated via `openapi-typescript` from the simulation service OpenAPI spec and should not be edited manually. The generated file covers request/response schemas for all REST endpoints.

**Route progress encoding**: `Trip.route` and `Trip.pickup_route` are full polyline arrays. `route_progress_index` and `pickup_route_progress_index` are integer offsets into those arrays, allowing incremental GPS ping updates to slice the rendered route efficiently without resending the entire geometry.

## Non-Obvious Details

- `WebSocketMessage` in `websocket.ts` is a discriminated union on `type` — all message handlers should use exhaustive narrowing against this union, not loose string checks.
- `GPSPing` carries `trip_state` (rider's fine-grained state) and `route_progress_index` (driver's route position) as optional fields to avoid separate update messages during active trips.
- `LayerVisibility` in `layers.ts` includes inline comments encoding the visual convention for each route type (color and line style), since the deck.gl layer construction is the only place these colors are formally defined.
- `is_ephemeral` and `is_puppet` flags on `DriverState`/`RiderState` distinguish simulation-managed agents from externally injected puppet agents; these affect what controls are available in the inspector UI.
- `real_time_ratio` on `SimulationStatus` is nullable — it is `null` when the simulation has not yet completed enough steps to compute a stable ratio.

## Related Modules

- [services/control-panel/src](../CONTEXT.md) — Reverse dependency — Provides App (default), theme (PALETTE, UI, OFFLINE, STAGE_RGB, STAGE_CSS, STAGE_HEX, injectCssVars), services/lambda (validateApiKey, triggerDeploy, getSessionStatus, getServiceHealth, etc.) (+2 more)
