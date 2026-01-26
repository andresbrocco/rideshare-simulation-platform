# Naming Conventions - Known Inconsistencies

This document tracks naming inconsistencies in the codebase. For standard naming patterns (`Repository`, `Handler`, `Manager`, etc.), these are self-evident from the codebase. See `docs/PATTERNS.md` for a quick reference.

## StateSnapshotManager Duplication

**Issue:** Two classes share the same name in different modules:
- `simulation/src/api/snapshots.py` - Reads state from engine for API
- `simulation/src/redis_client/snapshots.py` - Stores state in Redis for streaming

**Workaround:** Always use absolute imports to avoid ambiguity:
```python
from src.api.snapshots import StateSnapshotManager as APISnapshotManager
from src.redis_client.snapshots import StateSnapshotManager as RedisSnapshotManager
```

**Future Consideration:** Could rename to `EngineSnapshotManager` and `RedisSnapshotManager` in a future refactoring pass.

## MatchingServer Semantic Mismatch

**Issue:** The class doesn't serve HTTP requests; it manages the matching lifecycle.
**Pattern Fit:** Would be better suited to `MatchingManager` suffix.
**Status:** Accepted inconsistency - renaming would cause significant import churn with minimal benefit.

## Trip Class Duplication

**Issue:** Two classes named `Trip`:
- `simulation/src/trip.py` - Domain model with state machine logic
- `simulation/src/db/schema.py` - SQLAlchemy ORM model

**Status:** Accepted - different purposes in different layers.

## ErrorStats Class Duplication

**Issue:** Two classes named `ErrorStats`:
- `simulation/src/metrics/collector.py` - Internal metrics collection
- `simulation/src/api/models/metrics.py` - API response model

**Status:** Accepted - different purposes (internal vs API contract).
