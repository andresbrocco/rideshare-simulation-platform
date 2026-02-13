# CONTEXT.md — São Paulo Geographic Data

## Purpose

Geographic reference data for the ride-sharing simulation, providing official São Paulo district boundaries and zone-specific demand parameters. This data enables zone-based agent placement, surge pricing calculations, and spatial validation throughout the simulation.

## Responsibility Boundaries

- **Owns**: Official district boundaries (96 zones from GeoSampa), demand multipliers and surge sensitivity per subprefecture, simplified GeoJSON geometries for performance
- **Delegates to**: `src/geo/zones.py` for parsing and loading, `src/agents/zone_validator.py` for validation logic, DBT models for dimensional modeling
- **Does not handle**: Zone assignment logic (handled by geo module), surge pricing calculations (handled by matching server), runtime state or caching

## Key Concepts

### District vs Subprefecture Hierarchy
São Paulo is administratively organized into 32 subprefectures, each containing multiple districts. The simulation uses 96 districts as zones but inherits demand parameters from their parent subprefecture.

### Demand Multipliers
Zone-specific multipliers (0.5-2.0) that adjust the base probability of trip requests. Higher values (e.g., 1.7 for Pinheiros) represent affluent areas with more ride-sharing activity. Lower values (e.g., 0.5 for Parelheiros) represent peripheral areas with lower demand.

### Surge Sensitivity
Parameter (0.8-1.5) controlling how aggressively surge pricing responds to supply/demand imbalances in each zone. Higher sensitivity means surge pricing activates more easily in that zone.

### Geometry Simplification
Raw GeoJSON from GeoSampa undergoes two-pass Visvalingam simplification (1% per pass) to reduce file size while preserving boundary accuracy for point-in-polygon checks.

## Non-Obvious Details

### MultiPolygon Handling
Some districts in the raw GeoSampa data are MultiPolygons (containing multiple disjoint areas). The fetch script converts these to single Polygons by selecting the largest polygon by area, as the simulation's ZoneLoader only supports Polygon geometries.

### Three Files, One Source of Truth
- `distritos-sp-raw.geojson`: Original unmodified data from GeoSampa (archived for reference)
- `distritos-sp-simplified.geojson`: Intermediate file after geometry simplification
- `zones.geojson`: Final authoritative file with transformed properties and simplified geometries (this is the source of truth)

### Configuration Separation
Demand and surge parameters live in `subprefecture_config.json` rather than being hardcoded, allowing tuning without regenerating geometries. The fetch script merges this config into `zones.geojson` during transformation.

### Zone IDs Use District Abbreviations
Zone IDs (e.g., "PIN" for Pinheiros, "MOO" for Mooca) are three-letter abbreviations from the official GeoSampa dataset, not custom identifiers. These IDs are used throughout the system for partitioning, foreign keys, and visualization.
