# CONTEXT.md — Inspector

## Purpose

Provides on-demand detail popups for map entities — drivers, riders, and zones. When a user clicks an entity on the deck.gl map, the relevant inspector is rendered inside a floating draggable popup, showing live state fetched from the simulation API alongside contextual action controls.

## Responsibility Boundaries

- **Owns**: Rendering of entity detail panels (`DriverInspector`, `RiderInspector`, `ZoneInspector`), the draggable popup shell (`DraggablePopupContainer`), state-aware action buttons (`DriverActionsSection`, `RiderActionsSection`), and shared layout primitives (`InspectorSection`, `InspectorRow`, `StatsGrid`)
- **Delegates to**: Parent components for data fetching and action callbacks (inspectors are fully controlled — they receive state and emit events via props); `useDraggable` hook for drag positioning logic; formatter utilities (`formatDriverStatus`, `formatTripState`, etc.) for display text
- **Does not handle**: Data fetching, API calls, or state management — all callbacks (`onAcceptOffer`, `onStartTrip`, etc.) are injected by the parent

## Key Concepts

- **Puppet vs autonomous duality**: Each inspector checks `state.is_puppet`. Puppet agents show a live `Actions` section (accept/reject offer, start/cancel trip, toggle online status). Autonomous agents show `PreviousActionsSection` and `NextActionsSection` instead — read-only windows into the simulation's planned and past decisions.
- **Two-tier agent state**: The map layer uses lightweight `Driver`/`Rider` types (position, status only). Full `DriverState`/`RiderState` (DNA, statistics, active trip, pending offer) is fetched separately and passed as `state`. The inspectors handle the `state === null` / `loading` / `error` degraded states by falling back to the lightweight type for minimal display.
- **State machine–aware action buttons**: `DriverActionsSection` reads `pending_offer`, `active_trip`, and `status` simultaneously to determine which buttons to surface. Offer accept/reject only appears when a `pending_offer` exists; "Start Trip" only appears when `active_trip.state === 'at_pickup'`; "Cancel" when status is `en_route_pickup` or `on_trip`; online/offline toggle only when idle (no offer or trip).

## Non-Obvious Details

- `DraggablePopupContainer` initialises its position from the map click coordinates (`x`, `y` props) then manages internal drag state. Dragging is only activated when the mouse-down originates on the `.dragHandle` element — clicks on buttons or content do not initiate drag.
- The popup hardcodes `popupWidth: 320` and `popupHeight: 100` as drag boundary hints passed to `useDraggable`, not as CSS dimensions. Actual sizing is controlled by CSS.
- Currencies are displayed as Brazilian Reais (`R$`) throughout — consistent with the São Paulo simulation locale.
- `InspectorRow` accepts `React.ReactNode` as `value`, allowing `RiderInspector` to embed inline JSX (e.g., the driver status description next to the driver name) without a dedicated component.
- Rating display is suppressed (`'-'`) when `rating_count === 0` to avoid showing a meaningless default value before any trips complete.

## Related Modules

- [services/control-panel/src/components](../CONTEXT.md) — Reverse dependency — Provides Map, ControlPanel, InspectorPopup (+19 more)
