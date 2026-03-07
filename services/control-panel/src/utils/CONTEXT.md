# CONTEXT.md — Utils

## Purpose

Cross-cutting utility functions for the control panel frontend. Covers display formatting, domain-state label mapping, map visualization math, color interpolation for deck.gl layers, multi-subdomain cookie-based authentication, and a browser logger that emits structured JSON in production.

## Responsibility Boundaries

- **Owns**: All pure transformation and formatting logic consumed by components, hooks, and layers
- **Delegates to**: `types/api` (for domain enum types used in status label maps), browser APIs (`document.cookie`, `window.location`)
- **Does not handle**: State management, API calls, or React lifecycle

## Key Concepts

- **Status formatters** (`driverStatusFormatter`, `riderStatusFormatter`, `tripStateFormatter`): Each file maintains a complete `Record<EnumValue, string>` label map typed against the canonical API types — adding or renaming an API status will cause a TypeScript error here, making these files the compile-time coupling point between the API contract and the UI display strings.
- **Surge color scale** (`colorScale.ts`): Maps surge multiplier (1.0–2.5) to a yellow→orange→red RGB gradient using two-segment linear interpolation. Values outside the range are clamped. Output is an `[R, G, B]` tuple as required by deck.gl layer color props. `getSurgeOpacity` scales opacity from 0.2 to 0.6 over the same range.
- **Zoom scale** (`zoomScale.ts`): Converts a continuous map zoom level to a size multiplier using `layerZoomScaleFactor ^ (zoom - referenceZoom)`, anchored at zoom 11 (default Sao Paulo view). This allows deck.gl layer radii and widths to remain visually consistent across zoom levels without layer-specific zoom callbacks.
- **Auth cookie strategy** (`auth.ts`): The app runs on two separate subdomains (`ridesharing.portfolio.andresbrocco.com` for the landing page and `control-panel.ridesharing.portfolio.andresbrocco.com` for the app). A shared cookie scoped to the parent domain (`ridesharing.portfolio.andresbrocco.com`) carries the API key across both. `getAppMode()` detects which subdomain is active to drive routing behavior. In local development (neither subdomain), mode is `'dev'`.

## Non-Obvious Details

- `redirectToLanding()` uses `window.location.replace()` (not `href`) to prevent the control panel from being reachable via the browser back button after logout.
- The logger reads `VITE_LOG_LEVEL` at construction time (not per-call), so the level cannot be changed at runtime without a page reload. JSON output is enabled only in `import.meta.env.PROD`.
- `formatNumber` and `formatPercent` treat both `null` and `undefined` as missing, and also guard against non-finite values (e.g., `Infinity`, `NaN`), returning the configurable `fallback` string (default `'-'`).
- `colorUtils.ts` exports `RgbTuple` and `RgbaQuad` types — these are the canonical color types used by deck.gl layer props throughout the layers directory.

## Related Modules

- [services/control-panel/src](../CONTEXT.md) — Reverse dependency — Provides App (default), theme (PALETTE, UI, OFFLINE, STAGE_RGB, STAGE_CSS, STAGE_HEX, injectCssVars), services/lambda (validateApiKey, triggerDeploy, getSessionStatus, getServiceHealth, etc.) (+2 more)
