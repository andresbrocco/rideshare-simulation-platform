# CONTEXT.md — Control Panel src

## Purpose

Root source directory for the React frontend. Contains the application entry point, top-level routing between three distinct app modes, the centralized theme system, and shared cross-cutting modules (services, utils, constants, lib). Sub-directories hold components, hooks, layers, types, and contexts.

## Responsibility Boundaries

- **Owns**: Application mode selection (landing / control-panel / dev), auth cookie handoff between subdomains, top-level state wiring, theme tokens and CSS variable injection, Lambda service client, DNA preset definitions
- **Delegates to**: `components/` for all rendered UI, `hooks/` for state and data-fetching logic, `layers/` for deck.gl layer construction, `types/` for shared TypeScript types, `contexts/` for React context providers
- **Does not handle**: WebSocket protocol details (delegated to `hooks/useWebSocket`), map rendering (delegated to `components/Map`), simulation API calls (delegated to `hooks/useSimulationControl`)

## Key Concepts

**App modes** — The app serves three distinct runtime personalities, determined purely by `window.location.hostname`:

- `landing`: served at `ridesharing.portfolio.andresbrocco.com`; shows the public landing page + deploy workflow; auth cookie is set here and carried cross-subdomain.
- `control-panel`: served at `control-panel.ridesharing.portfolio.andresbrocco.com`; reads the cookie on mount, transfers the API key to `sessionStorage`, then immediately clears the cookie. If no auth is found, redirects back to landing using `replace()` (not `href`) to prevent back-button loops.
- `dev`: any other hostname (localhost); polls API health via `useApiHealth` and renders the full combined UI without cookie mechanics.

**Cross-subdomain auth handoff** — The cookie is set with `Domain=ridesharing.portfolio.andresbrocco.com` so it is visible on both the root domain and the `control-panel.` subdomain. The control-panel page consumes it exactly once, calls `storeSession()` to migrate the key into `sessionStorage` (with placeholder role/email), and clears the cookie via `clearAuthCookie()`. Subsequent same-tab reloads read from `sessionStorage` via `getApiKey()` directly.

**Theme system** — `theme.ts` is the single source of truth for all colors. It exports four layered regions: stage colors (trip lifecycle states, dual-format as hex, RGB tuples, and CSS strings for use in both deck.gl and HTML), a unified palette (neutral scale + four hue scales), a UI palette (semantic aliases for component styling), and an offline palette (landing page). `injectCssVars()` in `main.tsx` writes all palette values to `:root` as CSS custom properties before the first render, including `--var-rgb` companion variables for `rgba()` usage in CSS modules.

**Lambda service client** (`services/lambda.ts`) — All public-facing production operations (API key validation, deploy trigger, teardown, session management, service health) go through a single AWS Lambda function dispatched via POST with an `action` field. This decouples the frontend from directly calling EKS services from the browser. The `callLambda` generic helper performs runtime type narrowing on responses via discriminated validator functions.

**DNA presets** — `constants/dnaPresets.ts` defines preset behavioral profiles for puppet agents (drivers and riders). DNA parameters mirror the simulation engine's agent DNA model. `PlacementMode` drives the map click-to-place flow for injecting puppet agents at arbitrary coordinates.

## Non-Obvious Details

- **StrictMode is intentionally disabled** in `main.tsx` due to a race condition between React's double-mount behavior in StrictMode and deck.gl/luma.gl WebGL device initialization. Double-mounting causes `ResizeObserver` to fire before the WebGL context is ready.
- **`useSessionExpiry`** in `OnlineApp` listens for a `'session:expired'` custom DOM event dispatched by the API client on any 401 response. When fired, it calls `clearSession()` and shows the `LoginDialog`. This keeps the 401-handling path decoupled from individual request sites — no hook or service needs to know about the React auth state.
- **`LoginDialog` replaces `PasswordDialog`** — the dialog component was renamed from `PasswordDialog` to `LoginDialog` and its authentication flow was updated: it now calls `POST /auth/login` with `{email, password}`, receives `{api_key, role, email}`, and persists the full session via `storeSession()`. The old `PasswordDialog` validated a raw API key against Lambda directly; `LoginDialog` uses the simulation API's auth endpoint instead.
- **`usePageRefresh`** triggers a full `window.location.reload()` on a configurable interval (`VITE_PAGE_REFRESH_INTERVAL_MS`, default 10 minutes). This is a deliberate defense against long-running WebSocket sessions accumulating stale state.
- **`control_panel` health in `getServiceHealth`** is aliased to `simulation_api` health — if the simulation API is up, the control panel is considered healthy too (they are co-located on the same EKS deployment).
- **Destination selection mode** — requesting a rider trip is a two-step UI flow: selecting a rider opens the inspector popup, clicking "Request Trip" enters destination selection mode (a banner renders with a cancel button), and the next map click is interpreted as the destination coordinate rather than an entity click.
- **Zone surge data** — zones come from `useZones` (static GeoJSON), while surge multipliers come from the WebSocket stream via `useSimulationState`. They are merged in `useMemo` inside `OnlineApp` to produce `ZoneData[]` passed to the map layers.

## Related Modules

- [services/control-panel/src/components](components/CONTEXT.md) — Dependency — Top-level UI components for the simulation control panel and public portfolio la...
- [services/control-panel/src/contexts](contexts/CONTEXT.md) — Dependency — React context provider for frontend performance metrics (WebSocket message throu...
- [services/control-panel/src/hooks](hooks/CONTEXT.md) — Dependency — Custom React hooks encapsulating WebSocket real-time state management, REST poll...
- [services/control-panel/src/layers](layers/CONTEXT.md) — Dependency — deck.gl layer factories for the live simulation map, encoding trip lifecycle pha...
- [services/control-panel/src/types](types/CONTEXT.md) — Dependency — Central TypeScript type definitions for simulation domain entities, WebSocket me...
- [services/control-panel/src/utils](utils/CONTEXT.md) — Dependency — Cross-cutting utility functions for formatting, domain-state label mapping, map ...
