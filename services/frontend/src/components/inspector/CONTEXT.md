# CONTEXT.md — Inspector

## Purpose

Provides detailed inspection panels for simulation entities (drivers, riders, zones) as draggable popups on the map. Displays real-time state, behavioral DNA, session statistics, and puppet control actions for interactive testing.

## Responsibility Boundaries

- **Owns**: Entity detail rendering, puppet action buttons, inspector layout components
- **Delegates to**: Parent components for API calls and state management, useDraggable hook for positioning
- **Does not handle**: Data fetching (uses provided props), WebSocket subscriptions, or map interactions

## Key Concepts

**Puppet vs Autonomous Agents**: Inspectors distinguish between puppet agents (user-controlled via action buttons) and autonomous agents (display "Next Action" predictions). Only puppets show interactive controls.

**Behavioral DNA**: Immutable agent parameters displayed in dedicated sections (acceptance rates, patience thresholds, service quality). These are distinct from mutable profile attributes.

**Action State Machine**: Driver and rider action buttons are conditionally rendered based on current state (e.g., "Accept Offer" only shown when pending_offer exists, "Start Trip" only when driver_arrived).

## Non-Obvious Details

The DraggablePopupContainer restricts drag interaction to the dedicated drag handle (:::::: icon) to prevent conflicts with scrolling or button clicks within the popup content. The minimize feature collapses content while preserving the header for quick restoration.

Action sections use separate components (DriverActionsSection, RiderActionsSection) to encapsulate complex conditional button logic based on trip state, preventing the main inspector components from becoming cluttered with state machine branching.

## Related Modules

- **[services/simulation/src/api/routes](../../../../simulation/src/api/routes/CONTEXT.md)** — FastAPI puppet control endpoints that inspector action buttons invoke; buttons trigger commands like accept-offer or drive-to-pickup
- **[services/simulation/src/agents](../../../../simulation/src/agents/CONTEXT.md)** — Agent DNA and state structures displayed in inspectors; DNA parameters shown in behavioral sections
- **[src/components](../CONTEXT.md)** — Parent component layer that manages inspector popup state and provides data via props
