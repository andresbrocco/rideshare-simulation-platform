# CONTEXT.md — Utils

## Purpose

Cross-cutting utility functions for the control panel frontend. Covers display formatting, domain-state label mapping, map visualization math, color interpolation for deck.gl layers, sessionStorage-based authentication with cross-subdomain cookie hand-off, a thin authenticated fetch wrapper, and a browser logger that emits structured JSON in production.

## Responsibility Boundaries

- **Owns**: All pure transformation and formatting logic consumed by components, hooks, and layers; authenticated API fetch wrapper (`apiFetch`); session read/write helpers (`getApiKey`, `getSessionRole`, `getSessionEmail`, `storeSession`, `clearSession`)
- **Delegates to**: `types/api` (for domain enum types used in status label maps), browser APIs (`sessionStorage`, `document.cookie`, `window.location`, `window.dispatchEvent`)
- **Does not handle**: State management, React lifecycle, or response parsing beyond status checks

## Key Concepts

- **Status formatters** (`driverStatusFormatter`, `riderStatusFormatter`, `tripStateFormatter`): Each file maintains a complete `Record<EnumValue, string>` label map typed against the canonical API types — adding or renaming an API status will cause a TypeScript error here, making these files the compile-time coupling point between the API contract and the UI display strings.
- **Surge color scale** (`colorScale.ts`): Maps surge multiplier (1.0–2.5) to a yellow→orange→red RGB gradient using two-segment linear interpolation. Values outside the range are clamped. Output is an `[R, G, B]` tuple as required by deck.gl layer color props. `getSurgeOpacity` scales opacity from 0.2 to 0.6 over the same range.
- **Zoom scale** (`zoomScale.ts`): Converts a continuous map zoom level to a size multiplier using `layerZoomScaleFactor ^ (zoom - referenceZoom)`, anchored at zoom 11 (default Sao Paulo view). This allows deck.gl layer radii and widths to remain visually consistent across zoom levels without layer-specific zoom callbacks.
- **Auth strategy** (`auth.ts`): The app uses two separate auth stores. `sessionStorage` is the primary in-session store (`apiKey`, `role`, `email` keys); `storeSession`/`clearSession` manage it. A cross-subdomain cookie scoped to `ridesharing.portfolio.andresbrocco.com` handles the landing-page → control-panel hand-off only; cookie helpers (`setAuthCookie`, `getAuthCookie`, `clearAuthCookie`) are used for that one-time transfer. `getAppMode()` detects which subdomain is active to drive routing behavior. In local development (neither subdomain), mode is `'dev'`.
- **API fetch wrapper** (`apiClient.ts`): `apiFetch(path, init?)` is the single entry point for all REST calls from components and hooks. It reads the API key from `sessionStorage` via `getApiKey()`, injects the `X-API-Key` header, and — on a 401 response — calls `clearSession()` and dispatches a `session:expired` custom event on `window` so the React tree can redirect without coupling to the router. The base URL is read from `VITE_API_URL` (defaults to `http://localhost:8000`).

## Non-Obvious Details

- `redirectToLanding()` uses `window.location.replace()` (not `href`) to prevent the control panel from being reachable via the browser back button after logout.
- `apiFetch` dispatches `session:expired` on `window` before returning the 401 response — callers still receive the response object and can inspect it, but the event fires synchronously before the `await` resolves to allow global listeners to react immediately.
- Session storage keys (`apiKey`, `role`, `email`) are module-private constants in `auth.ts` — no other file should read from `sessionStorage` directly; always use the exported helpers.
- The logger reads `VITE_LOG_LEVEL` at construction time (not per-call), so the level cannot be changed at runtime without a page reload. JSON output is enabled only in `import.meta.env.PROD`.
- `formatNumber` and `formatPercent` treat both `null` and `undefined` as missing, and also guard against non-finite values (e.g., `Infinity`, `NaN`), returning the configurable `fallback` string (default `'-'`).
- `colorUtils.ts` exports `RgbTuple` and `RgbaQuad` types — these are the canonical color types used by deck.gl layer props throughout the layers directory.

## Related Modules

- [services/control-panel/src](../CONTEXT.md) — Reverse dependency — Provides App (default), theme (PALETTE, UI, OFFLINE, STAGE_RGB, STAGE_CSS, STAGE_HEX, injectCssVars), services/lambda (validateApiKey, triggerDeploy, getSessionStatus, getServiceHealth, etc.) (+2 more)
