# Kafka Topic Partitioning Strategy

This document explains the **rationale** behind partitioning decisions. For actual partition counts and retention settings, see the `kafka-init` service in `infrastructure/docker/compose.yml`.

## Overview

Kafka partitions determine how messages are distributed across a topic. The partition key controls which partition receives each message - messages with the same key always go to the same partition, guaranteeing ordering for that key.

## Partition Key Selection Rationale

| Topic | Partition Key | Rationale |
|-------|---------------|-----------|
| `trips` | `trip_id` | All events for a trip (requested → completed) are processed in order |
| `gps_pings` | `entity_id` | Pings for a driver/rider stay chronologically ordered |
| `driver_status` | `driver_id` | Status transitions for a driver are ordered |
| `surge_updates` | `zone_id` | Surge changes for a zone are ordered |
| `ratings` | `trip_id` | Groups rider and driver ratings for the same trip |
| `payments` | `trip_id` | One payment per trip |
| `driver_profiles` | `driver_id` | Profile updates for a driver are ordered |
| `rider_profiles` | `rider_id` | Profile updates for a rider are ordered |

## Ordering Guarantees

### trips

All events for a single trip are delivered in order:
- `REQUESTED` → `OFFER_SENT` → `MATCHED` → `DRIVER_EN_ROUTE` → `DRIVER_ARRIVED` → `STARTED` → `COMPLETED`

Different trips can be processed in parallel.

### gps_pings

Pings for a single entity (driver or rider) are chronologically ordered. This ensures GPS track reconstruction is accurate.

### driver_status

Status transitions for a driver are ordered. Without this, a driver could appear to go offline before going online.

### surge_updates

Surge multiplier changes for a zone are ordered. Consumers always see the latest surge value.

### ratings

Ratings for a trip are grouped together. Order doesn't matter since both rider and driver can rate independently.

### payments

One payment event per completed trip. No ordering concerns.

### profiles

Profile updates use SCD Type 2 semantics. Updates for a single driver/rider are ordered to maintain version history.

## Consumer Group Sizing

The number of partitions limits maximum parallelism - a consumer group cannot have more active consumers than partitions. Plan partition counts based on expected consumer parallelism:

- `gps_pings`: High partition count allows many parallel consumers (high volume)
- `trips`: Moderate parallelism
- Low volume topics: Fewer partitions to reduce overhead
