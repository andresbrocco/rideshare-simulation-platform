# Error Handling Guidelines

This document describes the standardized error handling patterns used throughout the simulation platform.

## Exception Hierarchy

All custom exceptions inherit from `SimulationError`:

```
SimulationError
├── TransientError (retry-worthy)
│   ├── NetworkError (timeout, connection refused)
│   └── ServiceUnavailableError (5xx from external services)
├── PermanentError (don't retry)
│   ├── ValidationError (bad input)
│   ├── NotFoundError (entity doesn't exist)
│   ├── StateError (invalid state transition)
│   └── ConfigurationError (missing/invalid config)
└── FatalError (crash immediately)
```

## When to Use Each Exception Type

### TransientError

Use for errors that may succeed on retry:

- **NetworkError**: Connection timeouts, refused connections, DNS failures
- **ServiceUnavailableError**: 5xx HTTP responses from external services, broker unavailable

```python
from core.exceptions import NetworkError, ServiceUnavailableError

if response.status_code >= 500:
    raise ServiceUnavailableError(f"Service returned {response.status_code}")
```

### PermanentError

Use for errors that will never succeed on retry:

- **ValidationError**: Invalid input data, malformed requests
- **NotFoundError**: Entity doesn't exist (driver, rider, trip)
- **StateError**: Invalid state transitions (e.g., completing a cancelled trip)
- **ConfigurationError**: Missing required config, invalid settings

```python
from core.exceptions import ValidationError, NotFoundError

if not user_exists(user_id):
    raise NotFoundError(f"User {user_id} not found")
```

### FatalError

Use for unrecoverable errors requiring shutdown:

- Database corruption
- Critical dependency failure (e.g., can't connect to database at startup)

## Retry Utility

The `with_retry` function provides exponential backoff for async operations:

```python
from core import with_retry, RetryConfig, NetworkError

config = RetryConfig(
    max_attempts=3,
    base_delay=0.5,       # seconds
    multiplier=2.0,       # exponential backoff
    max_delay=30.0,       # cap delay at 30s
    retryable_exceptions=(NetworkError,),
)

result = await with_retry(
    lambda: fetch_data(),
    config=config,
    operation_name="fetch_data",
)
```

For synchronous code, use `with_retry_sync`.

## Error Handling by Layer

### OSRM Client (geo/osrm_client.py)

- `NoRouteFoundError` → `ValidationError` (non-retryable)
- `OSRMServiceError` → `ServiceUnavailableError` (retryable)
- `OSRMTimeoutError` → `NetworkError` (retryable)

### Kafka Producer (kafka/producer.py)

- `KafkaProducerError` → `NetworkError` (retryable)
- Uses internal retry for buffer errors

### Trip Executor (trips/trip_executor.py)

Catches errors by category:

```python
except PermanentError as e:
    # Immediate cleanup, no retry
    self._cleanup_failed_trip(reason="permanent_error", ...)
except TransientError as e:
    # Log and cleanup (retries already attempted)
    self._cleanup_failed_trip(reason="transient_error", ...)
except Exception as e:
    # Unknown error, full logging
    logger.exception(f"Unexpected error in trip {trip_id}")
    self._cleanup_failed_trip(reason="unexpected_error", ...)
```

### Event Emitter (agents/event_emitter.py)

Fire-and-forget for non-critical events:

```python
except NetworkError as e:
    logger.warning(f"Kafka emit failed: {e}")
    # Continue without re-raising
```

## Logging Levels

| Exception Type | Log Level | Action |
|----------------|-----------|--------|
| TransientError (during retry) | WARNING | Continue retrying |
| TransientError (exhausted) | ERROR | Fail operation |
| PermanentError | ERROR | Fail immediately |
| FatalError | CRITICAL | Shutdown |
| Unknown Exception | ERROR + traceback | Fail with details |

## Adding Details to Exceptions

Include context for debugging:

```python
raise NetworkError(
    "Connection refused",
    details={"host": host, "port": port, "timeout": timeout}
)
```

Access via `error.details` in handlers.
