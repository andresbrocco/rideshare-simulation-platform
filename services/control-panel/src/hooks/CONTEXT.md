# CONTEXT.md — Frontend Hooks

## Purpose

Custom React hooks that encapsulate state management, data fetching, WebSocket communication, and visualization layer composition for the ride-sharing simulation control panel.

## Responsibility Boundaries

- **Owns**: State synchronization between WebSocket events and React component state, API polling for metrics, deck.gl layer composition, drag-and-drop UI interactions
- **Delegates to**: API client logic (plain fetch), WebSocket protocol handling, deck.gl layer factory functions
- **Does not handle**: Business logic validation, authentication implementation, raw data transformation

## Key Concepts

- **GPS Buffering**: `useSimulationState` batches GPS ping updates into 100ms windows to reduce React re-renders by ~10x. Uses a flush timeout to accumulate position updates before triggering a single setState.
- **Event Deduplication**: `useWebSocket` maintains an LRU cache of event IDs (max 1000) to prevent duplicate event processing when events arrive out of order or are retransmitted.
- **Stale State Guards**: `useSimulationState` prevents race conditions where late-arriving GPS pings revert trip state from 'offline' back to 'started' after trip completion.
- **Abort Signal Cleanup**: All polling hooks (`useMetrics`, `useInfrastructure`, `usePerformanceMetrics`, `useAgentState`) use AbortController to cancel in-flight requests on unmount, preventing memory leaks and state updates on unmounted components.
- **Ref-based Callbacks**: `useWebSocket` stores callbacks in refs updated via useLayoutEffect to ensure the WebSocket event handlers always reference the latest callback without recreating the connection.

## Non-Obvious Details

- `useSimulationState` merges trip updates with existing cached routes to preserve route geometry when updates don't include full route data, preventing visual flickering.
- `useAgentState` pauses polling when the detail panel is minimized to reduce API load.
- `useSimulationLayers` calculates zoom-based scale factors for icon sizing and applies layer ordering with zones/heatmaps at lowest pick priority and agents at highest pick priority for reliable click interactions.
- `usePerformanceContext` is a thin wrapper that throws an error if used outside the PerformanceProvider, enforcing proper context usage.
