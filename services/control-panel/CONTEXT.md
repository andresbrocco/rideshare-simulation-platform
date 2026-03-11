# CONTEXT.md — Control Panel

## Purpose

React/TypeScript single-page application that serves as the operator interface for the rideshare simulation. It provides a real-time geospatial map (deck.gl over MapLibre GL), simulation lifecycle controls, per-agent inspection, layer visibility management, and a landing/portfolio page. In production it is deployed as static assets to S3 served via CloudFront; in development it runs as a Vite dev server inside Docker.

## Responsibility Boundaries

- **Owns**: All UI rendering, WebSocket message consumption, deck.gl layer composition, agent placement interactions, auth cookie handoff between landing and control-panel pages, the visitor email consent form (`VisitorAccessForm`), the login dialog (`LoginDialog`), and the Vite dev-server proxy configuration.
- **Delegates to**: `services/simulation` REST/WebSocket API for simulation state and control commands; a Lambda function (`VITE_LAMBDA_URL`) for deploy/teardown orchestration, visitor provisioning (`provisionVisitor`), and auth key validation; `src/hooks/useRole` for role resolution; `src/hooks/useSessionExpiry` for 401-triggered session expiry handling.
- **Does not handle**: Business logic, event production, data persistence, or WebSocket message generation — it is a pure consumer.

## Key Concepts

- **Tri-modal app (`AppContent`)**: The application runs in one of three modes determined at startup by `getAppMode()`: `landing` (standalone portfolio page served from a separate route or subdomain), `control-panel` (the operator view, expects auth cookie injected by the landing page), and `dev` (combined local development mode that polls API health and renders both). Each mode is its own root component (`LandingApp`, `ControlPanelApp`, `DevApp`).
- **Auth cookie handoff**: Because landing and control-panel are served as separate "pages" (different paths or origins), auth cannot cross as React state. When the user authenticates on the landing page the API key is written to a short-lived cookie via `setAuthCookie`. `ControlPanelApp` reads the cookie on mount, calls `storeSession()` to migrate the key into `sessionStorage` (with placeholder role/email), and clears the cookie via `clearAuthCookie()`. Subsequent same-tab reloads read from `sessionStorage` via `getApiKey()` directly.
- **Puppet agents**: The UI can inject "puppet" drivers and riders (agents under direct operator control rather than autonomous simulation DNA). Puppet agents expose manual action buttons in the inspector (accept/reject offer, start trip, cancel trip) that fire REST commands.
- **Role-based access control**: `ControlPanel.tsx` reads the current role via `useRole()` and derives `isAdmin = role === 'admin'`. All simulation controls and puppet agent actions are disabled for non-admin users and show `'Admin only'` tooltips. The `isAdmin` flag is forwarded to `InspectorPopup` and ultimately to `DriverActionsSection`.
- **Visitor provisioning**: The `VisitorAccessForm` component (embedded in `LandingPage`) collects visitor email and consent, then calls `provisionVisitor(email)` from `src/services/lambda`. The Lambda action creates credentials and sends a confirmation email; the form handles partial-success (HTTP 207) by independently checking `provisioned` and `emailSent` fields.
- **`LoginDialog` replaces `PasswordDialog`**: The credential dialog was renamed and its auth flow updated. `LoginDialog.tsx` posts `{ email, password }` to `POST /auth/login`, receives `{ api_key, role, email }`, and persists the full session via `storeSession()`. The old `PasswordDialog` accepted a raw API key and validated it against Lambda directly.
- **Session expiry event**: `useSessionExpiry` in `OnlineApp` listens for a `'session:expired'` custom DOM event dispatched by `apiFetch` on any 401 response, calling `clearSession()` and showing `LoginDialog`. This keeps 401 handling decoupled from individual request sites.
- **Destination selection mode**: Requesting a trip for a rider is a two-step interaction: clicking "Request Trip" in the inspector popup enters destination-selection mode (the cursor changes, a banner appears), then a map click sends the trip request with the tapped coordinates. This state lives in `App` rather than in a hook to keep map click handling centralized.
- **`PerformanceContext`**: Wraps the entire app and tracks WebSocket message throughput and rendering frame rates. Used by performance monitoring panels; its provider must be the outermost wrapper so all hooks can consume it without prop-drilling.
- **Theme system**: `theme.ts` is the single source of truth for every color. It exposes three representations of each color: hex strings (for CSS), RGB tuples (for deck.gl `getColor` callbacks which require `[r, g, b]`), and CSS `rgb()` strings (for inline SVG/HTML). `injectCssVars()` bakes all values into CSS custom properties on `:root` before the first React render.

## Non-Obvious Details

- **StrictMode is disabled**: React StrictMode double-mounts components, which triggers a ResizeObserver before the deck.gl/luma.gl WebGL device is initialized, causing `"Cannot read properties of undefined (reading 'maxTextureDimension2D')"`. This is a known upstream deck.gl issue (visgl/deck.gl#9379). StrictMode must remain disabled until deck.gl resolves it.
- **Vite proxy rewrites**: In development the Vite server proxies `/api` → `http://simulation:8000`, `/ws` → `ws://simulation:8000`, and `/localstack` → `http://localstack:4566`. The proxy strips the prefix via `rewrite` and removes `Origin`/`Referer` headers on the LocalStack proxy to avoid CORS rejections. Production builds do not use the proxy — `VITE_API_URL`/`VITE_WS_URL` are baked into the bundle at build time via Vite's `import.meta.env`.
- **Docker node_modules seeding**: The Dockerfile pre-installs `node_modules` at image build time into `/tmp/node_modules`, then the entrypoint copies them into `/app/node_modules` only if the named volume is empty. This avoids a slow `npm install` on every cold container start while still supporting volume mounts for HMR.
- **TypeScript types generated from OpenAPI**: `src/types/api.generated.ts` is produced by `npm run generate-types`, which runs `openapi-typescript` against `schemas/api/openapi.json`. It should not be manually edited.
- **`zones.geojson` dependency**: The map's zone layer requires `public/zones.geojson`, which is sourced from `services/simulation/data/` via a Docker Compose bind mount in development. Production CI must widen the Docker build context to include that file before running `npm run build`.
- **Page auto-refresh**: `VITE_PAGE_REFRESH_INTERVAL_MS` (default 600 000 ms / 10 min) triggers a full `window.location.reload()`. This is a workaround to recover from long-running WebSocket drift or stale state in unattended demo sessions.

## Related Modules

- [infrastructure/scripts](../../infrastructure/scripts/CONTEXT.md) — Shares Authentication & Authorization domain (visitor provisioning)
- [infrastructure/terraform/foundation](../../infrastructure/terraform/foundation/CONTEXT.md) — Shares Authentication & Authorization domain (visitor provisioning)
- [schemas/api](../../schemas/api/CONTEXT.md) — Shares Agent Behavior & DNA domain (puppet agents)
- [services/control-panel/src/hooks](src/hooks/CONTEXT.md) — Shares Agent Behavior & DNA domain (puppet agents)
- [services/control-panel/src/hooks](src/hooks/CONTEXT.md) — Shares React Frontend Architecture domain (session expiry event)
- [services/control-panel/src/hooks](src/hooks/CONTEXT.md) — Shares Frontend State Management domain (session expiry event)
