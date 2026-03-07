# CONTEXT.md — Layers

## Purpose

Factories for all deck.gl map layers rendered on the live simulation map. Each function constructs a typed deck.gl layer (IconLayer, PathLayer, LineLayer, PolygonLayer, HeatmapLayer) from simulation state data, applying phase-based colors from the shared theme so the map encodes trip lifecycle visually.

## Responsibility Boundaries

- **Owns**: Layer construction, color mapping per agent/trip state, coordinate transformation, route-progress trail splitting, route-split cache lifecycle
- **Delegates to**: `../theme` for STAGE_RGB and STAGE_TRAIL color constants; `../utils/colorScale` for surge-to-color conversion; deck.gl for GPU rendering
- **Does not handle**: WebSocket data fetching, React state, map viewport, or layer composition/ordering (those live in the parent map component)

## Key Concepts

**Status-segregated layers**: deck.gl `IconLayer` cannot vary `iconAtlas` per data item, so drivers and riders are split into one layer per status/trip-state. The `createDriverLayer` and `createRiderLayer` functions group agents by status and return arrays of layers, while the individual `createOnlineDriversLayer` / `createOfflineDriversLayer` etc. functions return single layers for cases where only one status is needed.

**Coordinate convention mismatch**: Simulation backend stores routes as `[lat, lon]` arrays. deck.gl expects `[lon, lat]`. Every layer that renders route polylines calls `swapCoordinates` before passing paths to deck.gl. The route-split cache stores both the original and swapped forms to avoid re-swapping on every render.

**Route-split cache**: `agentLayers.ts` maintains a module-level `Map` keyed on `{tripId}:{routeType}:{progressIndex}` that caches the completed/remaining split of each route segment plus the swapped coordinate forms. The cache is evicted per-trip on completion/cancellation (`evictTripFromRouteCache`) and cleared entirely on simulation reset (`clearRouteCache`). Eviction uses a simple front-20% deletion when the 1000-entry limit is reached — not true LRU.

**Trail rendering pattern**: Active routes are rendered as two overlapping PathLayers — a faded "completed" trail (already traversed, non-pickable) and a solid "remaining" path (still to travel, pickable). Progress is tracked via `route_progress_index` / `pickup_route_progress_index` integer fields on the `Trip` object.

**Blinking matching line**: `createMatchingLineLayer` accepts a `blinkOn: boolean` and sets alpha to 220 or 0, producing a blinking effect when the caller alternates the flag. Used to visualize offer negotiation between a specific driver and rider.

**Icon tinting**: Car and person icons are monochrome white PNGs with `mask: true`. deck.gl applies `getColor` as a tint, so a single icon atlas supports all status colors.

## Non-Obvious Details

- `tripLayers.ts` exists as a legacy/unused thin wrapper (`createTripLayer`) that does not apply the progress-split or status-filter logic found in `agentLayers.ts`. The canonical route rendering functions are all in `agentLayers.ts`.
- The heading angle formula `90 - heading` converts from compass bearing (clockwise from north) to deck.gl's counter-clockwise-from-east convention.
- `createOfflineRidersLayer` is a catch-all: it renders riders whose `trip_state` is null/undefined OR any state not in `ACTIVE_TRIP_STATES`. This prevents riders from disappearing if an unexpected state arrives from the backend.
- Zone surge color and opacity are computed independently via `surgeToColor` / `getSurgeOpacity` and composed into a single RGBA tuple — opacity encodes surge intensity separately from hue.

## Related Modules

- [services/control-panel/src](../CONTEXT.md) — Reverse dependency — Provides App (default), theme (PALETTE, UI, OFFLINE, STAGE_RGB, STAGE_CSS, STAGE_HEX, injectCssVars), services/lambda (validateApiKey, triggerDeploy, getSessionStatus, getServiceHealth, etc.) (+2 more)
- [services/control-panel/src/components](../components/CONTEXT.md) — Reverse dependency — Provides Map, ControlPanel, InspectorPopup (+19 more)
