# Frontend

> Real-time geospatial visualization and control interface for rideshare simulation

## Quick Reference

### Environment Variables

| Variable       | Description             | Default                  | Required |
| -------------- | ----------------------- | ------------------------ | -------- |
| `VITE_API_URL` | Simulation API base URL | `http://localhost:8000`  | Yes      |
| `VITE_WS_URL`  | WebSocket endpoint URL  | `ws://localhost:8000/ws` | Yes      |

**Local Development:**
Copy `.env.example` to `.env` and adjust URLs if needed.

### Commands

```bash
# Development
npm install              # Install dependencies
npm run dev              # Start development server (port 5173)

# Testing
npm run test             # Run tests with Vitest
npm run test -- --watch  # Watch mode
npm run test -- --coverage  # With coverage

# Code Quality
npm run typecheck        # TypeScript type checking
npm run lint             # ESLint linting
npm run lint:fix         # Auto-fix lint issues
npm run format           # Format with Prettier
npm run format:check     # Check formatting

# Build
npm run build            # Build for production (tsc + vite build)
npm run preview          # Preview production build
```

### Ports

| Port | Service         | Description                    |
| ---- | --------------- | ------------------------------ |
| 5173 | Vite Dev Server | Development mode (HMR enabled) |
| 80   | Nginx           | Production mode (Docker)       |

**Docker Note:** Container exposes port 5173 internally, mapped to 5173 on host when running with Docker Compose.

### Configuration

| File               | Purpose                                                    |
| ------------------ | ---------------------------------------------------------- |
| `vite.config.ts`   | Vite build configuration, dev server settings, proxy rules |
| `vitest.config.ts` | Vitest test runner configuration                           |
| `eslint.config.js` | ESLint linting rules                                       |
| `tsconfig.json`    | TypeScript compiler options                                |
| `package.json`     | Dependencies and npm scripts                               |
| `.env.example`     | Environment variable template                              |

**Vite Proxy Rules:**

- `/api` → `http://simulation:8000` (REST API)
- `/ws` → `ws://simulation:8000` (WebSocket)

### Prerequisites

- Node.js 20+ (Alpine Linux in Docker)
- npm 10+
- Dependencies:
  - React 19.2.1 + TypeScript
  - deck.gl 9.2.5 (geospatial rendering)
  - react-map-gl 8.1.0 + MapLibre GL 5.14.0
  - Vite 7.2.4 (build tool)
  - Vitest 3.2.4 (testing)

## Common Tasks

### Start Development Server

```bash
# Local (recommended)
cd services/frontend
npm install
npm run dev
# Access at http://localhost:5173

# Docker Compose
docker compose -f infrastructure/docker/compose.yml --profile core up -d frontend
docker compose -f infrastructure/docker/compose.yml logs -f frontend
```

### Run Tests

```bash
cd services/frontend

# All tests
npm run test

# Watch mode (interactive)
npm run test -- --watch

# Coverage report
npm run test -- --coverage
```

### Authenticate with API

The frontend requires an API key to communicate with the simulation engine.

**Development Key:** `dev-api-key-change-in-production`

1. Start the frontend and backend
2. Login screen appears
3. Enter the development API key
4. Key is stored in sessionStorage

**How it works:**

- REST API: Sends `X-API-Key` header
- WebSocket: Uses `Sec-WebSocket-Protocol: apikey.<key>` header

### Debug WebSocket Connection

```bash
# Install wscat (if needed)
npm install -g wscat

# Connect directly to WebSocket
wscat -c "ws://localhost:8000/ws" -s "apikey.dev-api-key-change-in-production"

# Observe events
# Expected: driver-updates, rider-updates, trip-updates, surge_updates channels
```

### Build Production Bundle

```bash
cd services/frontend

# Type check first
npm run typecheck

# Build optimized bundle
npm run build

# Preview locally
npm run preview
```

Outputs to `dist/` directory. In production, Nginx serves these static files.

### Fix Lint/Format Issues

```bash
cd services/frontend

# Auto-fix ESLint issues
npm run lint:fix

# Format all code
npm run format

# Verify formatting
npm run format:check
```

Pre-commit hooks automatically run these checks.

## Troubleshooting

| Symptom                       | Cause                                     | Solution                                                                                                |
| ----------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| "WebSocket connection failed" | Simulation service not running            | Start simulation: `docker compose -f infrastructure/docker/compose.yml --profile core up -d simulation` |
| "API key required"            | Missing authentication                    | Enter `dev-api-key-change-in-production` in login screen                                                |
| Blank map / no tiles          | MapLibre GL CSS not loaded                | Check that `maplibre-gl` CSS is imported in `main.tsx`                                                  |
| HMR not working in Docker     | File watcher polling disabled             | Set `usePolling: true` in vite.config.ts (already configured)                                           |
| Port 5173 already in use      | Another Vite process running              | Kill existing process or change port in vite.config.ts                                                  |
| `npm install` fails in Docker | Platform mismatch (darwin/linux lockfile) | Dockerfile uses `npm install --force` to bypass platform checks                                         |

## Related

- [CONTEXT.md](CONTEXT.md) — Frontend architecture and design patterns
- [src/components/CONTEXT.md](src/components/CONTEXT.md) — React component structure
- [src/types/CONTEXT.md](src/types/CONTEXT.md) — TypeScript type definitions
- [../../CLAUDE.md](../../CLAUDE.md) — Project-wide development guide

---

## Additional Notes

> Preserved from original README.md

### Features

- **Interactive Map**: Deck.GL visualization with drivers, riders, zones, and routes
- **Real-Time Updates**: WebSocket connection with live state synchronization
- **Simulation Control**: Start/pause/reset, speed adjustment, agent spawning
- **Agent Inspector**: Click any agent to view detailed state, DNA, and statistics
- **Puppet Mode**: Manually control agents and step through trip lifecycles
- **Layer Management**: Toggle visibility of layer groups
- **Performance Monitoring**: WebSocket throughput, render FPS, latency metrics
- **Infrastructure Health**: Container status via cAdvisor integration

### Architecture

```
WebSocket → useWebSocket (dedup cache) → useSimulationState → useSimulationLayers → Deck.GL
     ↓
REST API → useSimulationControl → ControlPanel UI
```

#### Key Components

| Component                 | Purpose                                       |
| ------------------------- | --------------------------------------------- |
| `Map.tsx`                 | Deck.GL + MapGL container                     |
| `ControlPanel.tsx`        | Simulation controls (start/pause/reset/speed) |
| `InspectorPopup.tsx`      | Agent inspection overlay                      |
| `LayerControls.tsx`       | Layer visibility toggles                      |
| `PerformancePanel.tsx`    | Metrics dashboard                             |
| `InfrastructurePanel.tsx` | Container health monitoring                   |
| `LoginScreen.tsx`         | API key authentication                        |
| `AgentPlacement.tsx`      | Puppet mode agent placement                   |

#### Custom Hooks

| Hook                    | Purpose                                               |
| ----------------------- | ----------------------------------------------------- |
| `useWebSocket`          | WebSocket connection with reconnect and deduplication |
| `useSimulationControl`  | API calls to simulation engine                        |
| `useSimulationState`    | Centralized state management                          |
| `useSimulationLayers`   | Constructs deck.gl layers from state                  |
| `useAgentState`         | Individual agent state tracking                       |
| `useZones`              | Zone boundary and surge data                          |
| `useMetrics`            | Simulation metrics aggregation                        |
| `useInfrastructure`     | Container health via cAdvisor                         |
| `usePerformanceMetrics` | FPS, latency, throughput tracking                     |

#### Layer Groups

**Agents**: Drivers (by status), Riders (by state)
**Routes**: Pickup routes, Trip routes
**Zones**: Boundaries, Surge heatmap

### Project Structure

```
src/
├── components/         # React components
│   ├── inspector/      # Agent inspector sub-components
│   └── __tests__/      # Component tests
├── hooks/              # Custom React hooks
│   └── __tests__/      # Hook tests
├── layers/             # Deck.GL layer definitions
│   └── __tests__/      # Layer tests
├── types/              # TypeScript interfaces
├── contexts/           # React context providers
├── utils/              # Utility functions
│   └── __tests__/      # Utility tests
├── constants/          # DNA presets for puppet mode
├── lib/                # Third-party integrations
├── assets/             # Static assets
└── test/               # Test utilities and setup
```
