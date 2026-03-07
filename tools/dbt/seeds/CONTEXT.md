# CONTEXT.md — Seeds

## Purpose

Provides static geographic reference data for Sao Paulo's 96 administrative districts (subdistricts of the 32 subprefectures). This seed is the sole authoritative source for zone metadata used across the gold layer.

## Responsibility Boundaries

- **Owns**: Zone identity, geographic centroids, and simulation demand parameters for all Sao Paulo districts
- **Delegates to**: `dim_zones` (the dbt dimension model that adds a surrogate key and materializes this as a Gold table)
- **Does not handle**: H3 spatial indexing, zone assignment logic, or runtime zone state — those live in the simulation engine

## Key Concepts

- **zone_id**: A 3-letter uppercase code (e.g., `PIN` for Pinheiros, `IBI` for Itaim Bibi) used as the natural key throughout the event stream. Events emitted by the simulation carry these codes, not full names.
- **demand_multiplier**: A simulation parameter (range ~0.5–1.7) encoding relative rider demand density for each zone. Higher-valued zones (Pinheiros, Itaim Bibi, Moema) represent wealthier, higher-traffic areas.
- **surge_sensitivity**: A simulation parameter (range ~0.9–1.5) controlling how aggressively surge pricing responds in that zone. Peripheral zones with lower supply tend to have higher sensitivity.
- **centroid_latitude / centroid_longitude**: Approximate geographic center of each district, used by the simulation for spatial placement and distance calculations.

## Non-Obvious Details

- `demand_multiplier` and `surge_sensitivity` are not geographic facts — they are simulation tuning parameters embedded directly in this reference table. Changing them alters simulation behavior, not just analytics labels.
- The seed is joined by `fact_trips`, `fact_offers`, `fact_cancellations`, and `agg_surge_history` via `dim_zones`. Removing or renaming a zone_id here will break referential integrity tests across all four fact/aggregate models.
- Zone IDs in this seed must exactly match the zone IDs emitted by the simulation engine (defined in `services/simulation`). They are not derived from an external geospatial source — they were manually curated to match Sao Paulo's official district boundaries.

## Related Modules

- [tools/dbt/models](../models/CONTEXT.md) — Reverse dependency — Provides stg_trips, stg_gps_pings, stg_driver_status (+24 more)
