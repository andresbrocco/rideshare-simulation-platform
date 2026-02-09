# CONTEXT.md — Frontend

## Purpose

Real-time visualization and control interface for the rideshare simulation platform. Renders geospatial data using deck.gl/MapLibre and provides interactive controls for simulation lifecycle management and individual agent manipulation.

## Responsibility Boundaries

- **Owns**: Real-time map rendering, WebSocket state synchronization, user interaction with simulation entities, REST API calls for control actions
- **Delegates to**: Backend simulation engine for state management and event generation, stream processor for aggregated real-time updates via Redis pub/sub
- **Does not handle**: Simulation logic, trip matching, route calculation, event persistence

## Key Concepts

### State Management Architecture

- **WebSocket Connection** (`useWebSocket`): Connects with `apikey.<key>` subprotocol for authentication, includes event deduplication by `event_id`, automatic reconnection on disconnect
- **Simulation State** (`useSimulationState`): Maintains Maps (not arrays) for drivers/riders/trips for O(1) lookups, GPS ping buffering batches updates every 100ms to reduce re-renders by 10x, guards against stale GPS pings reverting completed trips to started state
- **Layer System** (`useSimulationLayers`): deck.gl layers composed by status/state with separate layers per icon atlas (deck.gl requirement), route split cache prevents redundant calculations, zoom-based scaling for visual consistency

### Performance Optimizations

- **Route Split Cache**: Memoizes completed/remaining route segments keyed by `tripId:routeType:progressIndex`, LRU eviction at 1000 entries, cleared on simulation reset
- **GPS Buffering**: Accumulates location updates in ref, flushes batch after 100ms timeout, reduces setState calls from thousands to tens per second
- **updateTriggers**: deck.gl dependency tracking uses stringified unique keys per entity to minimize layer recalculations

### Interactive Modes

- **Placement Mode**: Click-to-place puppet agents (drivers/riders) at map coordinates, cursor changes to crosshair
- **Destination Selection**: Two-step rider trip request (select rider from popup, then click destination on map)
- **Entity Inspector**: Popup displays agent DNA, statistics, active trip details, and action buttons for puppet control

## Non-Obvious Details

- **Coordinate Swap**: Backend uses `[lat, lon]` but deck.gl requires `[lon, lat]`, swap happens in layer functions
- **Trip State Guard**: Rider `trip_state` won't revert from `offline` to `started` on late GPS pings (race condition prevention)
- **Icon Atlas Limitation**: deck.gl IconLayer can't vary `iconAtlas` per datum, requires separate layers per status/state grouping
- **Route Progress Overlap**: Completed and remaining routes include the current progress point in both arrays for visual continuity
- **Event Deduplication**: Frontend caches last 1000 `event_id` values to handle potential duplicate WebSocket messages from reconnection windows
- **README Discrepancy**: Existing README is Vite template boilerplate, does not document this application's architecture or data flow

## Related Modules

- **[services/simulation](../simulation/CONTEXT.md)** — Simulation control partner; frontend issues lifecycle commands and puppet control via REST API, receives state updates
- **[services/stream-processor](../stream-processor/CONTEXT.md)** — Real-time data bridge; stream-processor aggregates events from Kafka and publishes to Redis channels that frontend subscribes to
- **[simulation/data](../simulation/data/CONTEXT.md)** — Geographic visualization layer; zone boundaries rendered on map enable spatial understanding of surge pricing and agent distribution
