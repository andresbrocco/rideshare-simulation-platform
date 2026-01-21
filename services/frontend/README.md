# Rideshare Simulation Control Panel

Real-time geospatial visualization and control interface for the rideshare simulation engine.

## Features

- **Interactive Map**: Deck.GL visualization with drivers, riders, zones, and routes
- **Real-Time Updates**: WebSocket connection with live state synchronization
- **Simulation Control**: Start/pause/reset, speed adjustment, agent spawning
- **Agent Inspector**: Click any agent to view detailed state, DNA, and statistics
- **Puppet Mode**: Manually control agents and step through trip lifecycles
- **Layer Management**: Toggle visibility of layer groups
- **Performance Monitoring**: WebSocket throughput, render FPS, latency metrics
- **Infrastructure Health**: Container status via cAdvisor integration

## Tech Stack

- React 19.2.1 + TypeScript
- deck.gl 9.2.5 (geospatial rendering)
- react-map-gl 8.1.0 + MapLibre GL 5.14.0
- Vite 7.2.4 (build tool)
- Vitest 3.2.4 (testing)

## Getting Started

```bash
# Install dependencies
npm install

# Start development server (port 5173)
npm run dev

# Build for production
npm run build

# Run tests
npm run test

# Type checking
npm run typecheck

# Linting
npm run lint
```

## Environment Variables

| Variable       | Description             | Default                  |
| -------------- | ----------------------- | ------------------------ |
| `VITE_API_URL` | Simulation API base URL | `http://localhost:8000`  |
| `VITE_WS_URL`  | WebSocket endpoint URL  | `ws://localhost:8000/ws` |

## Authentication

The app requires an API key for authentication:

- **Development**: `dev-api-key-change-in-production`
- Enter via login screen, stored in sessionStorage
- REST: `X-API-Key` header
- WebSocket: `Sec-WebSocket-Protocol: apikey.<key>`

## Architecture

```
WebSocket → useWebSocket (dedup cache) → useSimulationState → useSimulationLayers → Deck.GL
     ↓
REST API → useSimulationControl → ControlPanel UI
```

### Key Components

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

### Custom Hooks

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

### Layer Groups

**Agents**: Drivers (by status), Riders (by state)
**Routes**: Pickup routes, Trip routes
**Zones**: Boundaries, Surge heatmap

## Project Structure

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

## Testing

```bash
# Run all tests
npm run test

# Run tests in watch mode
npm run test -- --watch

# Run tests with coverage
npm run test -- --coverage
```

## Code Quality

```bash
# Type checking
npm run typecheck

# Linting
npm run lint

# Auto-fix lint issues
npm run lint:fix

# Format code
npm run format

# Check formatting
npm run format:check
```

## Docker

The frontend runs in Docker as part of the core profile:

```bash
# Start with core services
docker compose -f infrastructure/docker/compose.yml --profile core up -d

# View logs
docker compose -f infrastructure/docker/compose.yml logs -f frontend
```

Docker exposes port 3000 (mapped from internal 5173).
