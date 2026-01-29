# CONTEXT.md — Frontend

## Purpose

React-based real-time visualization frontend for the rideshare simulation platform. Displays drivers, riders, trips, and surge pricing on an interactive map using deck.gl, consuming WebSocket updates from the stream processor.

## Responsibility Boundaries

- **Owns**: Real-time map visualization, simulation control UI, agent inspection, performance metrics display
- **Delegates to**: Backend simulation API for control operations, stream processor for real-time updates via WebSocket, OSRM for route geometry
- **Does not handle**: Simulation logic, trip matching, route calculation, or state persistence (all backend responsibilities)

## Key Concepts

**GPS Ping Buffering**: Accumulates high-frequency GPS updates in a 100ms window before applying them in a single React state update. Reduces re-renders by ~10x compared to immediate setState.

**Route Split Cache**: Memoizes route calculations that split paths into completed (faded trail) and remaining (solid line) portions. Uses cache key `tripId:routeType:progressIndex` with LRU eviction at 1000 entries.

**Trip State Visualization**: Riders are colored by their position in the trip state machine (offline → requested → matched → driver_en_route → started → completed). Guards prevent stale GPS pings from reverting completed states.

**Agent Layers**: deck.gl IconLayer and PathLayer organized by visual priority. Agents render on top of routes, active states render above idle states. Coordinate transformation from [lat,lon] to [lon,lat] for deck.gl compatibility.

**WebSocket Event Deduplication**: Client-side cache of event_id values (max 1000) prevents duplicate processing when Redis pub/sub delivers the same event multiple times during reconnection.

**Puppet Agents**: User-created agents (via map clicks) that can be manually controlled through the inspector popup, distinct from autonomous AI agents.

## Non-Obvious Details

StrictMode is disabled at the root because it causes deck.gl/luma.gl WebGL initialization race conditions. Double-mounting triggers ResizeObserver before WebGL context is ready, causing "Cannot read properties of undefined (reading 'maxTextureDimension2D')" errors.

State is stored in Maps (not arrays) for O(1) lookups during high-frequency GPS ping updates. Arrays are generated via useMemo only when needed for rendering.

The PerformanceContext tracks frontend metrics (FPS, WebSocket msg/sec) using requestAnimationFrame and interval timers. Refs are initialized in useEffect (not render) to avoid impure renders.

WebSocket authentication uses subprotocol `apikey.<key>` format since custom headers aren't supported in browser WebSocket API.

useLayoutEffect updates callback refs before useEffect connection logic runs, ensuring handlers have the latest closures when messages arrive.

## Related Modules

- **[services/frontend/src/components](./components/CONTEXT.md)** — UI component implementations for control panel, map, inspector popups, and layer controls
- **[services/frontend/src/types](./types/CONTEXT.md)** — TypeScript contracts mirroring backend domain models and WebSocket message structure
- **[services/simulation/src/api/routes](../../simulation/src/api/routes/CONTEXT.md)** — Backend API endpoints for simulation control and agent manipulation
- **[services/stream-processor/src/handlers](../../stream-processor/src/handlers/CONTEXT.md)** — Transforms Kafka events into WebSocket messages consumed by frontend
