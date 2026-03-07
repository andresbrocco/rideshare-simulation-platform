# CONTEXT.md — Contexts

## Purpose

Provides React context for sharing frontend performance metrics (WebSocket message throughput and render FPS) across the component tree without prop drilling.

## Responsibility Boundaries

- **Owns**: Measurement of client-side performance metrics (`ws_messages_per_sec`, `render_fps`) and their distribution via React context
- **Delegates to**: Consumers (e.g., hooks, components) to call `recordWsMessage()` on each incoming WebSocket message
- **Does not handle**: Backend/simulation metrics, data fetching, WebSocket connection management

## Key Concepts

- **`FrontendMetrics`**: A type defined in `src/types/api` representing purely client-side measurements, distinct from server-side metrics reported by the simulation or stream processor.
- **`recordWsMessage`**: A stable callback (via `useCallback`) exposed from context that consumers call once per incoming WebSocket message; the provider internally batches counts and computes a per-second rate.

## Non-Obvious Details

- **Split file pattern**: The context object itself lives in `performanceContextDef.ts` (plain `.ts`) while the provider component lives in `PerformanceContext.tsx`. This separation is intentional — React hooks that consume the context can import from the definition file without importing the full provider, avoiding circular dependency chains.
- **`useRef` + `useState` split**: Message count and FPS frame count are stored in `useRef` (mutated without triggering renders), while only the computed rate values are stored in `useState`. This prevents excessive re-renders on every frame or every incoming WebSocket message.
- **FPS via `requestAnimationFrame`**: Render FPS is measured by scheduling a recursive `requestAnimationFrame` loop inside a `useEffect`. The `isActive` flag guards against state updates after unmount and properly cancels the animation frame on cleanup.
- **Time reference initialization in `useEffect`**: Both `lastWsCountTime` and `lastFpsTime` refs are initialized inside `useEffect` (not at declaration) to avoid impure render-time side effects.

## Related Modules

- [services/control-panel/src](../CONTEXT.md) — Reverse dependency — Provides App (default), theme (PALETTE, UI, OFFLINE, STAGE_RGB, STAGE_CSS, STAGE_HEX, injectCssVars), services/lambda (validateApiKey, triggerDeploy, getSessionStatus, getServiceHealth, etc.) (+2 more)
