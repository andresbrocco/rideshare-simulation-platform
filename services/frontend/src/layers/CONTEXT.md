# CONTEXT.md — Layers

## Purpose

Factory functions that create deck.gl layer instances for map visualization. Each function transforms domain data (drivers, riders, trips, zones) into configured deck.gl layers with appropriate styling, interactivity, and performance optimizations.

## Responsibility Boundaries

- **Owns**: Layer instantiation, visual styling rules, coordinate transformation, route progress splitting, layer-specific caching
- **Delegates to**: deck.gl for rendering, parent components for data fetching and state management, color utility functions for surge visualization
- **Does not handle**: WebSocket data flow, simulation state management, API communication

## Key Concepts

**Layer Separation by Status**: Drivers and riders are split into multiple layers grouped by status/state because deck.gl IconLayer requires a single iconAtlas per layer. Each status group gets a separate layer with pre-colored icon assets.

**Route Progress Visualization**: Active trips display four distinct route segments: completed pickup trail (faded pink), remaining pickup route (dashed pink), completed trip trail (faded blue), and remaining trip route (solid blue). Progress is tracked via `pickup_route_progress_index` and `route_progress_index`.

**Coordinate Swap**: OSRM routes arrive as `[lat, lon]` but deck.gl requires `[lon, lat]`. All path layers call `swapCoordinates()` to transform coordinates before rendering.

**Route Split Cache**: LRU cache (max 1000 entries) stores pre-computed route splits and coordinate transformations. Cache keys combine trip ID, progress index, and route type. Cleared on simulation reset via exported `clearRouteCache()`.

**Pre-Colored Icons**: Icon assets are pre-colored PNGs (e.g., `car-green.png`, `person-orange.png`) rather than dynamically tinted to ensure reliable rendering across browsers and deck.gl versions.

## Non-Obvious Details

The `updateTriggers` configuration is critical for performance. It tells deck.gl which attributes changed so only affected properties are recalculated. For position updates, we serialize IDs and coordinates into strings to create unique trigger values.

Route split caching implements simple LRU eviction by deleting the oldest 20% of entries when capacity is reached. This prevents unbounded memory growth during long-running simulations.

Driver and rider layers use different sizing strategies: drivers range 20-40px (more prominent), riders range 10-24px (smaller to reduce visual clutter). Scale factors can be applied to adjust all sizes proportionally for different zoom levels.

Destination flags use `anchorY: 100` to position the flag pole at the dropoff point, making the flag appear planted at the location rather than floating above it.
