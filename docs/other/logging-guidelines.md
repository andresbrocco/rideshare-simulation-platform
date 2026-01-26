# Logging Guidelines

For logging setup and implementation details, see `services/simulation/src/sim_logging/`. This document provides guidance on when to use each log level.

## Log Levels

| Level    | Use For                                          | Examples                           |
|----------|--------------------------------------------------|------------------------------------|
| DEBUG    | Verbose diagnostics, loop iterations, per-driver | Driver search iterations, ETA calc |
| INFO     | Lifecycle events, startup, major state changes   | Trip matched, service started      |
| WARNING  | Recoverable issues, fallbacks, degraded service  | Kafka unavailable, retry attempts  |
| ERROR    | Failures requiring investigation                 | Unhandled exceptions, data errors  |
| CRITICAL | System unusable, immediate action required       | Database down, out of memory       |
