# CONTEXT.md — Components

## Purpose

Top-level UI components for the control panel application. Covers two distinct surfaces: the simulation control panel (real-time map, agent inspection, stats) and the public landing/portfolio page (architecture overview, tech stack, deploy trigger). Components at this level are composed from hooks in `../hooks`, layer definitions in `../layers`, and services in `../services`.

## Responsibility Boundaries

- **Owns**: All rendered UI panels, the DeckGL+MapLibre map wrapper, the agent inspector popup, the deploy/session lifecycle panel, and the trip lifecycle animation
- **Delegates to**: `../hooks` for all data fetching and stateful logic, `../layers` for DeckGL layer construction, `../services/lambda` for cloud deployment API calls, `./inspector` subdirectory for per-entity inspector content
- **Does not handle**: WebSocket connection management, layer data computation, or raw API calls (all delegated to hooks)

## Key Concepts

**DeployPanel state machine** — `DeployPanel.tsx` owns a six-state lifecycle: `idle → deploying → active → tearing-down → expired → error`. It runs up to five concurrent polling intervals (workflow status, deploy progress, service health, session countdown tick, teardown progress). The `pendingDeployRef` / `pendingActionRef` pattern queues a deploy or session action if the user is not yet authenticated, then re-fires after auth completes.

**TripLifecycleAnimation direct-DOM rendering** — `TripLifecycleAnimation.tsx` bypasses React state entirely for its animation loop. All SVG element mutations happen via refs at 60fps using `requestAnimationFrame`. React state is never set during animation; the component uses `useRef` for all animated values. This is intentional to avoid re-render overhead. Phase logic is isolated in `tripLifecyclePhases.ts` as pure functions.

**Map click priority order** — `Map.tsx` handles clicks with explicit priority: (1) destination selection mode, (2) placement mode, (3) entity inspection. The click handler returns early after the first matching mode, so placement mode suppresses entity clicks entirely.

**InspectorPopup polling** — When an entity is selected, `InspectorPopup.tsx` polls the simulation API for live agent state via `useAgentState`. Polling is suspended when the popup is minimized. Home location coordinates arrive as `[lat, lon]` from the API but are swapped to `[lon, lat]` before passing to deck.gl (which expects longitude-first).

**LandingPage dual role** — `LandingPage.tsx` serves as both the public portfolio page and the entry point before authentication. It contains the tech stack showcase, architecture diagram embed, collapsible deep-dive sections, and the `DeployPanel` for on-demand cloud deployment. Service health badges are driven by `serviceHealth: ServiceHealthMap` passed from the parent; cards render as disabled `<span>` elements (not `<a>`) when their service is down to prevent broken navigation.

**LaunchDemoPanel vs DeployPanel** — `LaunchDemoPanel.tsx` is an older, simpler deploy component (4-step progress, local health polling only). `DeployPanel.tsx` is the current implementation with full session management, cost tracking, per-service progress, and extend/shrink controls. Both coexist because `LaunchDemoPanel` may still serve a different flow path.

## Non-Obvious Details

- `DeployPanel` derives partial service health from `deployProgress` during the `deploying` state (mapping deploy-progress service names to `ServiceHealthMap` keys via `DEPLOY_TO_HEALTH`). Real service health polling only starts after `transitionToActive`.
- When teardown completes and Lambda becomes unreachable, `DeployPanel` treats any `catch` during session polling as a signal that teardown finished — it transitions to `idle` rather than showing an error.
- The `wrapAction` helper in `InspectorPopup` sets a `isMountedRef` guard before calling `setActionLoading(false)` to prevent state updates on an unmounted component after async puppet actions complete.
- `TripLifecycleAnimation` respects `prefers-reduced-motion`: if the media query matches, it renders a static completed-state frame instead of running the animation loop.
- The `ConfirmModal` is used exclusively for the destructive reset action in `ControlPanel`; it is not a general-purpose modal.
- `SessionTimer` is a standalone countdown component distinct from the session timer logic inside `DeployPanel`; they serve different display contexts.

## Related Modules

- [services/control-panel/src](../CONTEXT.md) — Reverse dependency — Provides App (default), theme (PALETTE, UI, OFFLINE, STAGE_RGB, STAGE_CSS, STAGE_HEX, injectCssVars), services/lambda (validateApiKey, triggerDeploy, getSessionStatus, getServiceHealth, etc.) (+2 more)
- [services/control-panel/src/components/inspector](inspector/CONTEXT.md) — Dependency — On-demand entity detail popups for map-selected drivers, riders, and zones
- [services/control-panel/src/hooks](../hooks/CONTEXT.md) — Dependency — Custom React hooks encapsulating WebSocket real-time state management, REST poll...
- [services/control-panel/src/layers](../layers/CONTEXT.md) — Dependency — deck.gl layer factories for the live simulation map, encoding trip lifecycle pha...
