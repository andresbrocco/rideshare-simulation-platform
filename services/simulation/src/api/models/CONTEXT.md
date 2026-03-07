# CONTEXT.md — API Models

## Purpose

Defines all Pydantic request and response schemas for the simulation service's REST API. These models form the contract between the FastAPI route layer and external callers (control panel, test harness, CI scripts).

## Responsibility Boundaries

- **Owns**: Input validation, serialization shapes, field constraints for all API endpoints
- **Delegates to**: Route handlers (business logic), domain layer (actual agent/simulation state)
- **Does not handle**: Business logic, persistence, or internal domain model representations

## Key Concepts

**Puppet vs Autonomous agents**: Autonomous agents (`DriverCreateRequest`, `RiderCreateRequest`) are created in bulk and behave independently via SimPy. Puppet agents (`PuppetDriverCreateRequest`, `PuppetRiderCreateRequest`) are externally controlled one-at-a-time, accept partial DNA overrides, and support an `ephemeral` flag that skips SQLite persistence.

**DNA Override**: `DriverDNAOverride` and `RiderDNAOverride` express partial behavioral configuration — only the fields a caller wants to fix are set; `None` fields are filled from randomized defaults at spawn time. These override types are defined in `agents.py` but re-imported and re-used by `puppet.py`.

**Ephemeral flag**: When `ephemeral=True` (default for puppet agents), the created agent is not persisted to SQLite. This is used for testing and control-panel interaction where state retention across restarts is not needed.

**Simulation time vs wall time**: `NextActionResponse` exposes both `scheduled_at` (SimPy `env.now` simulation time, a float) and `scheduled_at_iso` (wall-clock ISO string) to allow callers to distinguish sim-time ordering from real-time display.

## Non-Obvious Details

- `__init__.py` exports only a subset of models defined across the five files. Many models in `metrics.py` (`PerformanceMetrics`, `InfrastructureResponse`, `StreamProcessorMetrics`, etc.) are intentionally not re-exported — routes import them directly from `api.models.metrics` rather than from the package namespace.
- `puppet.py` duplicates some shapes from `agents.py` (e.g., `PuppetDriverWithDNARequest` vs `PuppetDriverCreateRequest`) because the puppet endpoint adds a required `location` field not present in the autonomous-agent request. These are structurally similar but semantically distinct.
- `TripMetrics` includes per-reason cancellation breakdowns (`cancelled_no_drivers`, `cancelled_rider_before_pickup`, etc.) that map directly to cancellation reason enums in the engine layer — adding a new cancellation reason requires updating both.
- `SimulationStatusResponse` uses a `Literal` type for `state` with values `"stopped"`, `"running"`, `"draining"`, `"paused"` — these must stay in sync with the `SimulationState` enum in the engine.
