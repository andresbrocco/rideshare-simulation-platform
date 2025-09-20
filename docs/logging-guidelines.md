# Logging Guidelines

This document covers logging patterns for the rideshare simulation platform. The centralized logging module (`simulation/src/logging/`) provides structured formatters, PII filtering, and context propagation.

## Setup

Call `setup_logging()` at application startup. Use `SIM_LOG_LEVEL` to control verbosity and `LOG_FORMAT=json` for production environments. The setup configures root logger with appropriate filters (PII redaction, correlation IDs) and formatters.

```python
import os
from src.logging import setup_logging

setup_logging(
    level=os.environ.get("SIM_LOG_LEVEL", "INFO"),
    json_output=os.environ.get("LOG_FORMAT") == "json",
    environment=os.environ.get("ENVIRONMENT", "development"),
)
```

## Log Levels

| Level    | Use For                                          | Examples                           |
|----------|--------------------------------------------------|------------------------------------|
| DEBUG    | Verbose diagnostics, loop iterations, per-driver | Driver search iterations, ETA calc |
| INFO     | Lifecycle events, startup, major state changes   | Trip matched, service started      |
| WARNING  | Recoverable issues, fallbacks, degraded service  | Kafka unavailable, retry attempts  |
| ERROR    | Failures requiring investigation                 | Unhandled exceptions, data errors  |
| CRITICAL | System unusable, immediate action required       | Database down, out of memory       |

## Structured Logging

Use `extra={}` for context that should be machine-parseable:

```python
logger.info(
    f"Trip matched with driver",
    extra={"trip_id": trip.trip_id, "driver_id": driver.driver_id, "eta_seconds": eta}
)
```

## Context Managers

For operations spanning multiple log calls, use context managers:

```python
from src.logging import log_trip_context

with log_trip_context(trip_id=trip.trip_id, driver_id=driver.driver_id):
    logger.info("Starting pickup")  # trip_id and driver_id auto-added
    # ... multiple operations
    logger.info("Pickup complete")
```

## Environment Variables

| Variable       | Default     | Description                    |
|----------------|-------------|--------------------------------|
| SIM_LOG_LEVEL  | INFO        | DEBUG, INFO, WARNING, ERROR    |
| LOG_FORMAT     | text        | Set to `json` for JSON output  |
| ENVIRONMENT    | development | Included in JSON log records   |
