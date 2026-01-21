# ADR-002: Kafka-Only Event Publishing

## Status
Accepted

## Context
The simulation previously published events directly to both Kafka (for data pipelines) and Redis (for real-time frontend updates). This dual publishing pattern caused:
- Event duplication at the frontend
- Inconsistent timing between direct Redis and Kafka-based stream processor
- Bypass of stream processing logic
- Maintenance burden for two code paths

## Decision
Consolidate all event publishing to flow through Kafka only. The stream-processor service consumes from Kafka topics and publishes to Redis pub/sub channels for frontend consumption.

### Event Flow (Before)
```
Simulation → Kafka (data pipelines)
          → Redis (frontend) [DUPLICATE PATH]
```

### Event Flow (After)
```
Simulation → Kafka → Stream Processor → Redis → Frontend
```

### Kafka Reliability Tiers

**Tier 1 - Critical Events (trip state changes, payments):**
- Synchronous delivery confirmation via `flush(timeout=5.0)`
- Error logging and tracking in `_failed_deliveries`

**Tier 2 - High-Volume Events (GPS pings, driver status):**
- Fire-and-forget with error logging
- Graceful degradation

## Consequences

### Positive
- Single source of truth for all events
- No duplicate events at frontend
- Consistent event processing pipeline
- Stream processor can aggregate/filter/transform events

### Negative
- Slight latency increase (Kafka → stream processor → Redis vs direct Redis)
- Stream processor becomes critical path for frontend updates

### Mitigations
- Stream processor uses 100ms batching windows for efficiency
- Kafka buffering provides resilience during stream processor restarts
