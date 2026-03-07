# Control Panel

> React/TypeScript SPA providing a real-time geospatial operator interface for the rideshare simulation — live map, simulation lifecycle controls, agent inspection, and a portfolio landing page.

## Quick Reference

### Ports

| Port | Protocol | Description                         |
| ---- | -------- | ----------------------------------- |
| 5173 | HTTP     | Vite dev server (development)       |
| 80   | HTTP     | Nginx (production container target) |

### Environment Variables

All variables are prefixed `VITE_` and baked into the bundle at build time by Vite. Runtime values cannot be changed after `npm run build`.

| Variable                        | Dev default                                                | Production                                            | Purpose                                                   |
| ------------------------------- | ---------------------------------------------------------- | ----------------------------------------------------- | --------------------------------------------------------- |
| `VITE_API_URL`                  | `http://localhost:8000`                                    | `https://api.ridesharing.portfolio.andresbrocco.com`  | Base URL for REST API calls                               |
| `VITE_WS_URL`                   | `ws://localhost:8000/ws`                                   | `wss://api.ridesharing.portfolio.andresbrocco.com/ws` | WebSocket endpoint for real-time state                    |
| `VITE_LAMBDA_URL`               | `/localstack/2015-03-31/functions/auth-deploy/invocations` | Set by CI from `vars.LAMBDA_URL`                      | Lambda function URL for deploy/teardown/auth              |
| `VITE_LOG_LEVEL`                | `info`                                                     | —                                                     | Frontend log verbosity                                    |
| `VITE_PAGE_REFRESH_INTERVAL_MS` | `600000` (10 min)                                          | —                                                     | Full-page reload interval to recover from WebSocket drift |

Environment file load order (Vite convention):

```
npm run dev    → .env.development  (then .env.local overrides)
npm run build  → .env.production   (then .env.local overrides)
```

Do not commit `.env.local`. Never hardcode `VITE_API_KEY` — the API key is passed at runtime via auth cookie handoff (production) or entered in the dev UI.

### Dev Server Proxy

In development, Vite proxies these paths so the browser never hits CORS:

| Path prefix     | Forwards to              | Notes                                                         |
| --------------- | ------------------------ | ------------------------------------------------------------- |
| `/api/*`        | `http://simulation:8000` | Strips `/api` prefix                                          |
| `/ws/*`         | `ws://simulation:8000`   | WebSocket passthrough                                         |
| `/localstack/*` | `http://localstack:4566` | Strips `/localstack` prefix; drops `Origin`/`Referer` headers |

Production builds do not use the proxy — `VITE_API_URL` and `VITE_WS_URL` are embedded directly.

### Commands

Run all commands from `services/control-panel/`.

| Command                  | Purpose                                                                 |
| ------------------------ | ----------------------------------------------------------------------- |
| `npm run dev`            | Start Vite dev server with HMR on port 5173                             |
| `npm run build`          | Type-check then compile to `dist/`                                      |
| `npm run preview`        | Preview production build locally                                        |
| `npm run test`           | Run Vitest unit tests                                                   |
| `npm run lint`           | ESLint check                                                            |
| `npm run lint:fix`       | ESLint auto-fix                                                         |
| `npm run format`         | Prettier format all `src/**/*.{ts,tsx,css,json}`                        |
| `npm run typecheck`      | TypeScript type-check without emitting                                  |
| `npm run generate-types` | Regenerate `src/types/api.generated.ts` from `schemas/api/openapi.json` |

### Docker

| Target stage  | Command                                  | Output                                 |
| ------------- | ---------------------------------------- | -------------------------------------- |
| `development` | `docker compose ... up control-panel`    | Vite dev server on 5173 with HMR       |
| `builder`     | `docker build --target builder .`        | Production bundle in `/app/dist`       |
| `static`      | `docker build --target static -o dist .` | Raw static assets extracted to `dist/` |
| `production`  | `docker build --target production .`     | Nginx container serving on port 80     |

The `development` image pre-installs `node_modules` at build time and seeds a named volume on first start. This avoids slow `npm install` on cold container starts while keeping the volume mount available for HMR.

```bash
# Start with the full platform stack (includes control-panel)
docker compose -f infrastructure/docker/compose.yml \
  --profile core --profile data-pipeline --profile monitoring up -d

# Rebuild the control-panel image after dependency changes
docker compose -f infrastructure/docker/compose.yml build control-panel
```

### Configuration Files

| File                 | Purpose                                                                                          |
| -------------------- | ------------------------------------------------------------------------------------------------ |
| `vite.config.ts`     | Dev server settings, proxy rules, path aliases (`@` → `/src`)                                    |
| `tsconfig.json`      | TypeScript project references                                                                    |
| `tsconfig.app.json`  | App-level TypeScript config                                                                      |
| `tsconfig.node.json` | Node tooling TypeScript config                                                                   |
| `tailwind.config.js` | Tailwind CSS customization                                                                       |
| `postcss.config.js`  | PostCSS pipeline                                                                                 |
| `.env.development`   | Dev environment defaults (committed)                                                             |
| `.env.production`    | Production environment defaults (committed; `VITE_LAMBDA_URL` is a placeholder overridden by CI) |
| `.env.example`       | Documentation of all supported variables                                                         |
| `.env.local`         | Local overrides (gitignored)                                                                     |

### Prerequisites

- Node 20 (matches Dockerfile base image)
- `public/zones.geojson` — provided by a bind mount from `services/simulation/data/` in development. For production builds, the Docker build context must be widened to include this file before running `npm run build`.
- Simulation API running and reachable at `VITE_API_URL` for the control panel to display live data

## App Modes

The application selects one of three runtime modes based on `window.location.hostname`:

| Mode            | Hostname                                               | Description                                                                        |
| --------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `landing`       | `ridesharing.portfolio.andresbrocco.com`               | Public portfolio page + deploy/teardown workflow; sets auth cookie                 |
| `control-panel` | `control-panel.ridesharing.portfolio.andresbrocco.com` | Operator view; reads cookie on mount, moves key to `sessionStorage`, clears cookie |
| `dev`           | `localhost` (any other hostname)                       | Combined UI with API health polling; no cookie mechanics                           |

## Common Tasks

### Run locally in Docker

```bash
docker compose -f infrastructure/docker/compose.yml --profile core up -d control-panel
# Open http://localhost:5173
```

### Run outside Docker (bare Node)

```bash
cd services/control-panel
npm install
npm run dev
# Open http://localhost:5173
```

Set `VITE_API_URL` and `VITE_WS_URL` in `.env.local` to point at a running simulation instance.

### Build production assets for S3 deployment

```bash
cd services/control-panel
VITE_API_URL=https://api.ridesharing.portfolio.andresbrocco.com \
VITE_WS_URL=wss://api.ridesharing.portfolio.andresbrocco.com/ws \
VITE_LAMBDA_URL=https://<function-url>.lambda-url.us-east-1.on.aws/ \
npm run build
# Artifacts in dist/
```

Or use the Docker `static` target to extract the bundle:

```bash
docker build --target static -o dist \
  --build-arg VITE_API_URL=https://api.ridesharing.portfolio.andresbrocco.com \
  --build-arg VITE_WS_URL=wss://api.ridesharing.portfolio.andresbrocco.com/ws \
  --build-arg VITE_LAMBDA_URL=https://<function-url>.lambda-url.us-east-1.on.aws/ \
  services/control-panel/
```

### Regenerate API types after OpenAPI changes

```bash
cd services/control-panel
npm run generate-types
# Rewrites src/types/api.generated.ts — do not edit manually
```

### Run tests

```bash
cd services/control-panel
npm run test          # watch mode
npm run test -- --run # single pass (CI)
```

### Authenticate in dev mode

In `dev` mode (localhost) the app polls `GET /health` on `VITE_API_URL` and renders a key input field. Enter `admin` (the default key seeded via `seed-secrets.py`). The key is stored in `sessionStorage` for the tab lifetime only.

## Troubleshooting

### Blank map / WebGL crash on first load

React StrictMode is intentionally disabled. If you re-enable it, deck.gl's WebGL device initialization races with React's double-mount and throws `"Cannot read properties of undefined (reading 'maxTextureDimension2D')"`. Leave StrictMode disabled until this is resolved upstream (visgl/deck.gl#9379).

### `zones.geojson` not found / zone layer missing

The zone layer requires `public/zones.geojson`. In development this file is bind-mounted from `services/simulation/data/`. If the file is missing:

1. Ensure the simulation container has started and the bind mount is active.
2. Verify the compose volume section references `services/simulation/data/zones.geojson`.

### HMR not working inside Docker

The Vite server uses polling (`usePolling: true`) to detect file changes across the Docker bind mount. If HMR still does not trigger, confirm the host directory is bind-mounted into `/app/src`.

### node_modules empty after container restart

The Dockerfile seeds `node_modules` from a build-time cache into a named volume. If the volume exists but is corrupt or empty, remove the named volume and restart:

```bash
docker compose -f infrastructure/docker/compose.yml down -v
docker compose -f infrastructure/docker/compose.yml --profile core up -d control-panel
```

### WebSocket disconnects / stale state

The app auto-reloads every `VITE_PAGE_REFRESH_INTERVAL_MS` ms (default 10 min) as a defense against stale WebSocket state in long-running sessions. To disable this during development, remove or set `VITE_PAGE_REFRESH_INTERVAL_MS=0` in `.env.local`.

### Production build missing `zones.geojson`

For CI/production builds the Docker build context must include `services/simulation/data/zones.geojson`. Copy it into `services/control-panel/public/` before running `docker build` or widen the build context in the CI workflow.

### LocalStack Lambda proxy returns CORS errors

The Vite dev proxy removes `Origin` and `Referer` headers on `/localstack` requests. If you still see CORS errors, confirm the Vite dev server is being used (not a direct browser fetch to LocalStack) and that `VITE_LAMBDA_URL` starts with `/localstack/`.

## Related

- [CONTEXT.md](CONTEXT.md) — Architecture context: tri-modal app, auth cookie handoff, theme system, deck.gl integration
- [src/CONTEXT.md](src/CONTEXT.md) — Source directory overview: app modes, Lambda client, DNA presets, theme injection
- [src/hooks/CONTEXT.md](src/hooks/CONTEXT.md) — Custom hooks: WebSocket, simulation control, agent state
- [src/components/CONTEXT.md](src/components/CONTEXT.md) — UI components: map, inspector, landing page
- [schemas/api/CONTEXT.md](../../schemas/api/CONTEXT.md) — OpenAPI spec that drives `src/types/api.generated.ts`
- [services/simulation/src/api/routes/CONTEXT.md](../simulation/src/api/routes/CONTEXT.md) — REST/WebSocket endpoints this UI consumes
