# CONTEXT.md — Components

## Purpose

React components that compose the ride-sharing simulation control panel and real-time visualization interface. Responsible for displaying live agent states, trip progress, and geospatial data on a deck.gl map, as well as providing manual control for "puppet" agents.

## Responsibility Boundaries

- **Owns**: UI presentation layer, user interactions, real-time WebSocket state updates, deck.gl layer rendering, agent inspection popups
- **Delegates to**: Custom hooks in `../hooks/` for data fetching and WebSocket management, API client in `../api/` for agent actions
- **Does not handle**: Business logic, state management beyond UI state, data transformation beyond formatting for display

## Key Concepts

**Puppet vs Autonomous Agents**: The UI distinguishes between autonomous agents (controlled by behavioral DNA and scheduled actions) and puppet agents (manually controlled by the user through inspector actions). Puppet agents display action buttons instead of next action schedules.

**Inspector Popup System**: Clicking agents on the map opens draggable, minimizable popups that poll the API for up-to-date state. The popup shows DNA parameters, current trip details, session statistics, and context-sensitive action buttons for puppet control.

**Layer Visibility Control**: Users can toggle visibility of different agent states (online/offline drivers, waiting/in-transit riders) and routes (pending/pickup/trip routes) independently. The LayerControls component manages a LayerVisibility state object passed to the parent.

**Placement Mode**: When creating puppet agents, the UI enters a placement mode with crosshair cursor and banner instructions. Map clicks in this mode spawn agents at the clicked coordinates rather than selecting entities.

**Two-Phase Pause**: The ControlPanel reflects the simulation's "draining" state during pause, indicating in-flight trips are completing before full pause.

## Non-Obvious Details

**Map Performance**: The Map component explicitly finalizes the DeckGL instance on unmount to prevent WebGL context leaks. The WebSocket updates from Redis drive incremental layer data updates.

**Inspector State Polling**: The InspectorPopup uses `useAgentState` hook to poll `/api/drivers/{id}/state` or `/api/riders/{id}/state` every 2 seconds when not minimized. This ensures the displayed state stays synchronized with backend changes during manual puppet control.

**Action Loading States**: Inspector action buttons (accept offer, arrive at pickup, start trip, etc.) show loading state and trigger refetch after completion to immediately reflect state changes. The `wrapAction` pattern ensures cleanup even if the component unmounts mid-action.

**Destination Selection Flow**: Puppet riders can select destinations via map click. The parent sets `destinationMode={true}` on the Map component, which takes priority over placement mode and entity clicks, invoking `onDestinationSelect` callback.

**Stats Aggregation**: StatsPanel receives both real-time counts from WebSocket messages and metrics from API endpoints (`/api/metrics/*`). Real-time counts take precedence for display to minimize lag.

## Related Modules

- **[services/frontend/src/components/inspector](./inspector/CONTEXT.md)** — Detailed entity inspection panels with puppet control interfaces
- **[services/frontend/src/types](../types/CONTEXT.md)** — TypeScript type definitions for agent states, trips, and UI configuration
- **[services/simulation/src/api/routes](../../../simulation/src/api/routes/CONTEXT.md)** — Backend API providing control operations and state queries
