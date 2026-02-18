# Control Panel Frontend

> Real-time React web interface for visualizing and controlling the rideshare simulation, built with Vite, deck.gl, and MapLibre GL.

## Quick Reference

### Environment Variables

| Variable         | Purpose                | Default                  | Example                          |
| ---------------- | ---------------------- | ------------------------ | -------------------------------- |
| `VITE_API_URL`   | REST API base URL      | `http://localhost:8000`  | `http://localhost:8000`          |
| `VITE_WS_URL`    | WebSocket endpoint     | `ws://localhost:8000/ws` | `ws://localhost:8000/ws`         |
| `VITE_LOG_LEVEL` | Frontend logging level | `info`                   | `debug`, `info`, `warn`, `error` |

**Notes:**

- All `VITE_*` variables are bundled at build time (Vite convention)
- WebSocket requires `Sec-WebSocket-Protocol: apikey.<key>` header for authentication
- REST API requires `X-API-Key` header for authentication

### Docker Service

**Service name:** `control-panel`

```bash
# Start frontend (requires simulation service)
docker compose -f infrastructure/docker/compose.yml --profile core up -d control-panel

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f control-panel

# Stop frontend
docker compose -f infrastructure/docker/compose.yml --profile core down
```

**Access:** http://localhost:5173

**Health check:** HTTP GET to http://localhost:5173

**Depends on:**

- `simulation` service (API + WebSocket backend)

### API Endpoints (Backend)

The frontend consumes these endpoints from the `simulation` service:

#### Authentication

- `POST /auth/validate` - Validate API key

#### Simulation Control

- `GET /simulation/status` - Get simulation state
- `POST /simulation/start` - Start simulation
- `POST /simulation/pause` - Pause simulation
- `POST /simulation/resume` - Resume simulation
- `POST /simulation/reset` - Reset simulation
- `PUT /simulation/speed` - Set speed multiplier

#### Agent Management

- `POST /agents/drivers?mode={immediate|scheduled}` - Add drivers
- `POST /agents/riders?mode={immediate|scheduled}` - Add riders
- `GET /agents/drivers/{driver_id}` - Get driver state
- `GET /agents/riders/{rider_id}` - Get rider state
- `PUT /agents/drivers/{driver_id}/status` - Toggle driver online/offline

#### Puppet Agent Creation

- `POST /agents/puppet/drivers` - Create puppet driver
- `POST /agents/puppet/riders` - Create puppet rider

#### Puppet Driver Actions

- `POST /agents/puppet/drivers/{driver_id}/accept-offer` - Accept trip offer
- `POST /agents/puppet/drivers/{driver_id}/reject-offer` - Reject trip offer
- `POST /agents/puppet/drivers/{driver_id}/arrive-pickup` - Mark arrival at pickup
- `POST /agents/puppet/drivers/{driver_id}/start-trip` - Start trip
- `POST /agents/puppet/drivers/{driver_id}/complete-trip` - Complete trip
- `POST /agents/puppet/drivers/{driver_id}/cancel-trip` - Cancel trip

#### Puppet Rider Actions

- `POST /agents/puppet/riders/{rider_id}/request-trip` - Request trip with destination
- `POST /agents/puppet/riders/{rider_id}/cancel-trip` - Cancel trip

#### Testing Controls

- `PUT /agents/puppet/drivers/{driver_id}/rating` - Update driver rating
- `PUT /agents/puppet/riders/{rider_id}/rating` - Update rider rating
- `PUT /agents/puppet/drivers/{driver_id}/location` - Teleport driver
- `PUT /agents/puppet/riders/{rider_id}/location` - Teleport rider
- `POST /agents/puppet/drivers/{driver_id}/force-offer-timeout` - Force offer timeout
- `POST /agents/puppet/riders/{rider_id}/force-patience-timeout` - Force patience timeout

#### Metrics

- `GET /metrics/overview` - Overview metrics
- `GET /metrics/drivers` - Driver metrics
- `GET /metrics/riders` - Rider metrics
- `GET /metrics/trips` - Trip metrics
- `GET /metrics/infrastructure` - Infrastructure health metrics

#### WebSocket

- `WS /ws` - Real-time updates for drivers, riders, trips, and surge pricing

**Authentication:**

```bash
# REST API
curl -H "X-API-Key: admin" http://localhost:8000/simulation/status

# WebSocket (using wscat)
wscat -c ws://localhost:8000/ws --subprotocol "apikey.admin"
```

### Commands

#### Development

```bash
# Start dev server (requires backend running)
npm run dev

# Format code
npm run format

# Check formatting
npm run format:check
```

#### Build & Preview

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

#### Quality Checks

```bash
# Type checking
npm run typecheck

# Linting
npm run lint

# Fix linting issues
npm run lint:fix

# Run tests
npm run test
```

#### Code Generation

```bash
# Generate TypeScript types from OpenAPI spec
npm run generate-types
```

**Note:** Types are generated from `../../schemas/api/openapi.json` → `src/types/api.generated.ts`

### Configuration Files

| File                 | Purpose                                      |
| -------------------- | -------------------------------------------- |
| `vite.config.ts`     | Vite dev server, proxy, build config         |
| `tsconfig.json`      | TypeScript compiler options                  |
| `tsconfig.app.json`  | TypeScript config for app code               |
| `tsconfig.node.json` | TypeScript config for Vite config            |
| `eslint.config.js`   | ESLint rules (React, TypeScript)             |
| `.prettierrc`        | Code formatting rules                        |
| `package.json`       | Dependencies and scripts                     |
| `Dockerfile`         | Multi-stage build (dev, builder, production) |

### Prerequisites

- **Node.js 20+** (Alpine in Docker)
- **npm** (bundled with Node.js)
- **Backend:** `simulation` service running on port 8000
- **Map data:** `services/simulation/data/zones.geojson` (mounted via Docker)

## Common Tasks

### Start Development Environment

```bash
# 1. Start backend services first
docker compose -f infrastructure/docker/compose.yml --profile core up -d simulation

# 2. Start frontend
docker compose -f infrastructure/docker/compose.yml --profile core up -d control-panel

# 3. Access UI
open http://localhost:5173

# 4. Login with API key
# Default: admin
```

### Add Custom Environment Variables

```bash
# 1. Create .env file
cat > services/control-panel/.env << EOF
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
VITE_LOG_LEVEL=debug
EOF

# 2. Rebuild container (if using Docker)
docker compose -f infrastructure/docker/compose.yml --profile core up -d --build control-panel
```

**Note:** `.env` files are not checked into git. Use `.env.example` as a template.

### Update API Types

When the OpenAPI spec changes:

```bash
# 1. Update schemas/api/openapi.json
# 2. Regenerate TypeScript types
cd services/control-panel
npm run generate-types

# 3. Review changes
git diff src/types/api.generated.ts
```

### Debug WebSocket Connection

```bash
# Check frontend logs for WebSocket errors
docker compose -f infrastructure/docker/compose.yml logs -f control-panel

# Test WebSocket manually
npm install -g wscat
wscat -c ws://localhost:8000/ws --subprotocol "apikey.admin"

# Expected output:
# < {"type":"connected","data":{}}
# < {"type":"status","data":{"state":"running",...}}
```

### Profile Frontend Performance

The frontend includes a built-in performance monitor:

```typescript
import { usePerformanceContext } from './hooks/usePerformanceContext';

// In component:
const { recordWsMessage, metrics } = usePerformanceContext();

// Metrics tracked:
// - WebSocket message rate
// - Rendering FPS
// - Memory usage (if available)
```

### Run Tests Locally

```bash
cd services/control-panel

# Install dependencies (if not done)
npm install

# Run all tests
npm run test

# Run tests in watch mode
npm run test -- --watch

# Run tests with coverage
npm run test -- --coverage
```

### Deploy Production Build

```bash
# Build production image
docker build -t rideshare-control-panel:prod --target production services/control-panel/

# Run with Nginx
docker run -p 80:80 rideshare-control-panel:prod

# Access UI
open http://localhost
```

## Troubleshooting

### Frontend Won't Start

**Symptom:** `control-panel` exits immediately

**Solutions:**

```bash
# 1. Check if simulation service is healthy
docker compose -f infrastructure/docker/compose.yml ps simulation

# 2. Check logs for errors
docker compose -f infrastructure/docker/compose.yml logs control-panel

# 3. Rebuild with fresh dependencies
docker compose -f infrastructure/docker/compose.yml build --no-cache control-panel
```

### WebSocket Connection Fails

**Symptom:** "Disconnected" indicator in UI

**Solutions:**

```bash
# 1. Verify simulation service is running
curl -H "X-API-Key: admin" http://localhost:8000/simulation/status

# 2. Check CORS settings in simulation service
# See services/simulation/.env for CORS_ORIGINS

# 3. Verify WebSocket URL
echo $VITE_WS_URL  # Should be ws://localhost:8000/ws

# 4. Test WebSocket directly
wscat -c ws://localhost:8000/ws --subprotocol "apikey.admin"
```

### Map Doesn't Load

**Symptom:** Black screen or "Failed to load map" error

**Solutions:**

```bash
# 1. Check zones.geojson is mounted
docker compose -f infrastructure/docker/compose.yml \
  exec control-panel ls -lh /app/public/zones.geojson

# 2. Verify file permissions
# zones.geojson should be readable (644)

# 3. Check browser console for errors
# Look for 404 errors on /zones.geojson
```

### API Requests Return 401 Unauthorized

**Symptom:** All API calls fail with 401 status

**Solutions:**

```bash
# 1. Check API key is set in session storage
# Open browser DevTools → Application → Session Storage → apiKey

# 2. Verify API key is valid
curl -H "X-API-Key: admin" http://localhost:8000/auth/validate

# 3. Clear session storage and re-login
sessionStorage.clear()
```

### Build Fails with TypeScript Errors

**Symptom:** `npm run build` fails with type errors

**Solutions:**

```bash
# 1. Check for TypeScript errors
npm run typecheck

# 2. Regenerate API types
npm run generate-types

# 3. Clear TypeScript cache
rm -rf node_modules/.cache/
npm run build
```

### Hot Module Replacement (HMR) Not Working

**Symptom:** Changes not reflected without full page reload

**Solutions:**

```bash
# 1. Check Vite polling is enabled (required in Docker)
# vite.config.ts should have:
#   server: { watch: { usePolling: true } }

# 2. Ensure files are bind-mounted, not copied
# compose.yml should have:
#   volumes:
#     - ../../services/control-panel:/app

# 3. Restart dev server
docker compose -f infrastructure/docker/compose.yml restart control-panel
```

## Related

- [CONTEXT.md](CONTEXT.md) - Architecture and component design
- [services/simulation/README.md](../simulation/README.md) - Backend API reference
- [schemas/api/openapi.json](../../schemas/api/openapi.json) - OpenAPI specification
- [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - System-wide architecture
