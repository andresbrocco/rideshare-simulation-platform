# CONTEXT.md — Kafka Schemas

## Purpose

JSON Schema definitions for all Kafka events published by the rideshare simulation platform. These schemas are registered in Confluent Cloud Schema Registry and enforce data contracts between producers (simulation engine) and consumers (stream processors, data pipelines).

## Responsibility Boundaries

- **Owns**: Event structure definitions, field validation rules, enum values for event types and status values
- **Delegates to**: Schema Registry for version management and compatibility checks; producers/consumers for serialization/deserialization
- **Does not handle**: Event routing logic, topic partitioning strategy, or consumer group management

## Key Concepts

**Event Traceability Fields**: All schemas include optional `session_id` (simulation run), `correlation_id` (primary entity, typically trip_id), and `causation_id` (triggering event) fields for distributed tracing and event sourcing patterns.

**Reliability Tiers**: Events fall into two categories based on business criticality. Tier 1 (trip state changes, payments) require synchronous delivery confirmation. Tier 2 (GPS pings, driver status) use fire-and-forget with error logging.

**Profile Events**: `driver_profile_event` and `rider_profile_event` support both creation and update event types (`driver.created`, `driver.updated`, `rider.created`, `rider.updated`) for SCD Type 2 dimension tracking in the data warehouse.

## Non-Obvious Details

The `trip_event` schema covers 10 distinct trip states through a single event type with an enum field, rather than using separate event schemas per state. This design simplifies schema evolution while maintaining a complete audit trail of trip lifecycle transitions.

GPS ping events include `route_progress_index` and `pickup_route_progress_index` fields to enable percentage-complete calculations in real-time visualizations without requiring clients to store full route geometries.

Payment events include both `platform_fee_percentage` (0.0-1.0) and `platform_fee_amount` to preserve the exact fee calculation at transaction time, protecting against rounding errors during analytics aggregations.
