# CONTEXT.md — Agents

## Purpose

This module defines the autonomous actors in the rideshare simulation: drivers and riders. Each agent is a SimPy process with DNA-based behavioral parameters that control decision-making, lifecycle patterns, and event emission. Agents interact with the matching system, emit events to Kafka, and maintain runtime statistics.

## Responsibility Boundaries

- **Owns**: Agent state machines (driver statuses, rider trip lifecycle), DNA-based behavioral decision logic (offer acceptance, destination selection, shift patterns), GPS ping emission loops, event creation and Kafka publishing, session statistics tracking
- **Delegates to**: Matching system for trip offers and assignments, OSRM client for route calculations, Zone loader for geographic zone assignment, Surge calculator for pricing multipliers, Database repositories for state persistence, Stream processor for Redis pub/sub (via Kafka)
- **Does not handle**: Trip state management (delegated to Trip class), driver-rider matching algorithms (MatchingServer), route geometry generation (OSRMClient), surge pricing calculation logic (SurgePricingCalculator)

## Key Concepts

**DNA (Immutable Behavioral Parameters)**: Frozen Pydantic models defining agent personality that never changes during simulation. Driver DNA includes acceptance_rate, service_quality, avg_response_time, shift_preference. Rider DNA includes behavior_factor, patience_threshold, max_surge_multiplier. Profile attributes (contact info, vehicle details) can change via SCD Type 2 updates but DNA behavioral parameters remain constant.

**Agent Lifecycle Modes**: Three operational modes - Normal (shift-based autonomy following DNA patterns), Immediate (goes online immediately for testing), Puppet (manually controlled via API with no autonomous behavior). Puppet mode only emits GPS pings and responds to external commands.

**Event Flow Architecture**: Agents publish all events exclusively to Kafka topics (trips, gps_pings, driver_status, ratings, driver_profiles, rider_profiles). The separate stream-processor service consumes from Kafka and publishes to Redis pub/sub channels for WebSocket delivery to frontend. No direct Redis publishing from agents eliminates duplicate events.

**Statistics vs Persistence**: Statistics dataclasses track session-only metrics (trips_completed, total_earnings, offers_received) that reset on simulation restart. Persistence layer (repositories) maintains durable state (location, active_trip, current_rating) that survives checkpoints. Statistics are never persisted to database.

**GPS Ping Intervals**: Dynamic interval selection based on agent status. Moving agents (drivers en_route_pickup/en_route_destination, riders in_trip) use GPS_PING_INTERVAL_MOVING (default 2s) for smooth visualization and arrival detection. Idle drivers use GPS_PING_INTERVAL_IDLE (default 10s) to reduce event load.

**Zone Validation**: All locations (home, destinations, generated coordinates) must fall within São Paulo district zone boundaries. DNA validators use point-in-polygon checks against zones.geojson. Invalid locations raise ValueError during DNA creation preventing invalid agents from being instantiated.

## Non-Obvious Details

**Next Action Tracking**: The next_action property exposes scheduled future actions (NextActionType.GO_ONLINE, GO_OFFLINE, REQUEST_RIDE, PATIENCE_TIMEOUT) with scheduled_at timestamps for API inspection. This allows frontend to display "Driver goes offline in 2h" without predicting behavior. Cleared (set to None) during state transitions.

**Two-Phase Driver Offline**: When shift ends, driver waits for active_trip to complete before going offline (30-second polling loop). Prevents orphaned trips when driver tries to end shift mid-trip. GPS process is interrupted only after status changes to offline.

**Rider Patience Timeout**: Riders transition from "waiting" to "in_trip" immediately when driver goes en_route (on_driver_en_route callback), not when trip starts. This prevents patience timeout from cancelling trip while driver is driving to pickup. Timeout only applies during offer matching phase.

**Immediate Online Events**: Drivers with immediate_online=True emit initial GPS ping and status preview before run() process starts. Enables instant map visibility in frontend without waiting for SimPy process scheduling. Preview event uses trigger="creation_preview" to distinguish from actual go_online transition.

**Faker Brazilian Localization**: DNA generator uses custom Faker provider (faker_provider.py) with Brazilian-specific data: São Paulo mobile phone format (11 9XXXX-XXXX), Mercosur license plates, local vehicle makes (Volkswagen, Fiat, Chevrolet), Brazilian payment methods (Pix, credit card with BIN ranges).

**Haversine Distance Validation**: Rider frequent destinations must be within 20km of home_location using haversine_distance calculation. Validator runs after zone validation ensuring destinations are both inside valid zones and within reasonable distance. Prevents unrealistic cross-city commute patterns.

**Thread-Safe Event Loop Access**: Agents run in SimPy thread but emit events to Kafka via async coroutines on main thread's event loop. Uses asyncio.run_coroutine_threadsafe to schedule coroutines from SimPy thread, with fallback_sync=True in run_coroutine_safe for environments without running event loop.

**Rating Submission Probability**: Not all completed trips result in ratings. should_submit_rating() uses exponential distribution favoring submission of extreme ratings (1-star and 5-star have higher probability than 3-star). Implements realistic rating behavior where neutral experiences don't generate feedback.

## Related Modules

- **[src/matching](../matching/CONTEXT.md)** — Matching engine that agents interact with for ride requests; agents submit requests and respond to match offers
- **[src/engine](../engine/CONTEXT.md)** — SimPy orchestrator that manages agent process lifecycle; agents run as SimPy processes within the engine's environment
- **[src/events](../events/CONTEXT.md)** — Event factory for creating structured events; agents use EventFactory to emit standardized events to Kafka
- **[src/trips](../trips/CONTEXT.md)** — Trip execution coordinator; TripExecutor manages the journey after matching while agents track trip participation
- **[services/stream-processor/src](../../../stream-processor/src/CONTEXT.md)** — Consumes agent events from Kafka and routes to Redis for frontend WebSocket delivery
