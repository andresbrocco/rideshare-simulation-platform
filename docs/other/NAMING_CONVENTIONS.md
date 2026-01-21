# Naming Conventions

This document defines class naming patterns used across the codebase to maintain consistency and improve code discoverability.

## Class Naming Patterns

### Repository Pattern

**When to Use:** Database access layer classes
**Suffix:** `Repository`
**Responsibilities:** CRUD operations, queries, transactions
**Examples:** `DriverRepository`, `TripRepository`, `RiderRepository`

### Handler Pattern

**When to Use:** Event processing classes
**Suffix:** `Handler`
**Responsibilities:** Process messages, emit events, transform data streams
**Examples:** `TripHandler`, `DriverStatusHandler`, `GPSHandler`

### Manager Pattern

**When to Use:** Lifecycle coordination, resource pooling
**Suffix:** `Manager`
**Responsibilities:** Manages lifecycle of resources, owns multiple instances, coordinates state
**Examples:** `CheckpointManager`, `ConnectionManager`, `OfferTimeoutManager`
**Anti-pattern:** Don't use for pure utilities or stateless helpers

### Controller Pattern

**When to Use:** API-style command translation, external control interfaces
**Suffix:** `Controller`
**Responsibilities:** Translate external commands to internal actions
**Examples:** `PuppetDriveController`

### Service Pattern

**When to Use:** Stateful business logic with caching or external dependencies
**Suffix:** `Service`
**Responsibilities:** Business operations that may cache results or coordinate with external services
**Examples:** `RouteCacheService`, `ZoneAssignmentService`

### Client Pattern

**When to Use:** External service integration
**Suffix:** `Client`
**Responsibilities:** Wrap communication with external APIs or services
**Examples:** `OSRMClient`

### Other Patterns

| Suffix | Use Case | Examples |
|--------|----------|----------|
| `Registry` | In-memory lookup tables | `DriverRegistry`, `RiderRegistry` |
| `Calculator` | Pure computation without side effects | `SurgePricingCalculator` |
| `Publisher/Producer` | Message sending | `KafkaProducer` |
| `Executor` | Multi-step orchestration | `TripExecutor` |
| `Agent` | SimPy autonomous entities | `DriverAgent`, `RiderAgent` |
| `Engine` | Core orchestrators | `SimulationEngine` |
| `Index` | Specialized data structures | `DriverGeospatialIndex` |

## Known Inconsistencies

### StateSnapshotManager Duplication

**Issue:** Two classes share the same name in different modules:
- `simulation/src/api/snapshots.py` - Reads state from engine for API
- `simulation/src/redis_client/snapshots.py` - Stores state in Redis for streaming

**Workaround:** Always use absolute imports to avoid ambiguity:
```python
from src.api.snapshots import StateSnapshotManager as APISnapshotManager
from src.redis_client.snapshots import StateSnapshotManager as RedisSnapshotManager
```

**Future Consideration:** Could rename to `EngineSnapshotManager` and `RedisSnapshotManager` in a future refactoring pass.

### MatchingServer Semantic Mismatch

**Issue:** The class doesn't serve HTTP requests; it manages the matching lifecycle.
**Pattern Fit:** Would be better suited to `MatchingManager` suffix.
**Status:** Accepted inconsistency - renaming would cause significant import churn with minimal benefit.

### Trip Class Duplication

**Issue:** Two classes named `Trip`:
- `simulation/src/trip.py` - Domain model with state machine logic
- `simulation/src/db/schema.py` - SQLAlchemy ORM model

**Status:** Accepted - different purposes in different layers.

### ErrorStats Class Duplication

**Issue:** Two classes named `ErrorStats`:
- `simulation/src/metrics/collector.py` - Internal metrics collection
- `simulation/src/api/models/metrics.py` - API response model

**Status:** Accepted - different purposes (internal vs API contract).

## Guidelines for New Classes

1. **Choose the most specific pattern** - If a class is a Repository, use that suffix even if it also "manages" data.

2. **Avoid generic suffixes** - Names like `DataManager` or `Helper` are too vague. Be specific about what the class does.

3. **Check for existing classes** - Run the duplicate detection hook before committing to avoid name collisions.

4. **Document exceptions** - If you must deviate from conventions, add an entry to "Known Inconsistencies" above.
