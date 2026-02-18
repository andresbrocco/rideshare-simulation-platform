# CONTEXT.md — Types

## Purpose

TypeScript type definitions for the frontend application, representing the contract between the simulation backend, WebSocket stream, and React UI. These types mirror domain concepts from the simulation engine and define the shape of real-time data updates.

## Responsibility Boundaries

- **Owns**: TypeScript interfaces for all frontend data structures (agents, trips, metrics, WebSocket messages)
- **Delegates to**: Backend services define the canonical data structure; frontend types mirror these
- **Does not handle**: Data transformation logic (handled by hooks/stores) or validation (handled by backend)

## Key Concepts

**Agent DNA**: Immutable behavioral parameters assigned at agent creation. DriverDNA includes acceptance rates, vehicle info, and shift preferences. RiderDNA includes patience thresholds, surge tolerance, and frequent destinations.

**Trip State vs Status**: `TripStateValue` represents granular rider visualization states (requested, offer_sent, matched, driver_en_route, etc.) while `Trip.status` is a string field for backend state. The state machine has 10 states with specific transition rules.

**Route Progress Indices**: `route_progress_index` and `pickup_route_progress_index` enable efficient GPS ping updates by tracking position along pre-computed route geometry without re-sending entire polylines.

**WebSocket Message Types**: Discriminated union of 8 message types (snapshot, driver_update, rider_update, trip_update, surge_update, gps_ping, simulation_status, simulation_reset) where `type` field determines the shape of `data`.

**Layer Visibility**: Configuration object controlling which map layers render (driver states, rider states, route types, zone boundaries, surge heatmap). Used by deck.gl layer composition.

## Non-Obvious Details

**Dual State Snapshot Definitions**: `StateSnapshot` is defined in both `websocket.ts` and `api.ts` because WebSocket messages have a different structure (`{ type, data }`) than REST API responses. Import from the appropriate file based on usage context.

**Service Health Status**: Three-level enum (`healthy`, `degraded`, `unhealthy`) applies to both individual services (Redis, Kafka, OSRM) and overall system status. Stream processor health includes additional connection flags for Kafka and Redis.

**Performance Metrics Aggregation**: Latency metrics track avg/p95/p99 percentiles with sample counts. Event metrics measure throughput per second. Stream processor metrics include GPS aggregation ratio (how many GPS pings are batched before Redis publish).

**Agent Inspection Types**: `DriverState` and `RiderState` provide deep inspection of agent internals including DNA, statistics, active trips, pending offers, and next scheduled action. Used by agent detail modals.
