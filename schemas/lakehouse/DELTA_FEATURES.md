# Delta Lake Features for Bronze Layer

This document explains the Delta Lake features enabled on Bronze tables and their benefits.

## Features Overview

All Bronze Delta tables have the following features enabled:

1. **Change Data Feed (CDC)** - Tracks row-level changes for downstream processing
2. **Auto-Optimize** - Automatically optimizes file sizes during writes
3. **Auto-Compact** - Automatically consolidates small files
4. **Date-based Partitioning** - Partitions data by ingestion date for efficient queries

## Change Data Feed

### Purpose
Change Data Feed captures all row-level changes (INSERT, UPDATE, DELETE) to enable:
- Incremental processing in Silver layer
- Audit trails and compliance
- Time-travel queries to see historical changes

### Usage
Query the CDC feed using the `table_changes()` function:

```sql
-- Get all changes from version 0 onwards
SELECT *
FROM table_changes('delta.`s3a://rideshare-bronze/bronze_trips/`', 0)
WHERE _change_type IN ('insert', 'update_postimage', 'delete')
ORDER BY _commit_version, _commit_timestamp;

-- Get changes between specific timestamps
SELECT *
FROM table_changes('delta.`s3a://rideshare-bronze/bronze_trips/`',
  '2026-01-12 00:00:00', '2026-01-13 00:00:00')
```

### CDC Columns
- `_change_type`: insert, update_preimage, update_postimage, delete
- `_commit_version`: Delta table version number
- `_commit_timestamp`: Timestamp of the commit

## Auto-Optimize

### Purpose
Auto-optimize improves query performance by:
- **Optimized Writes**: Writes larger, more efficient files (target: 128MB)
- **Auto-Compact**: Consolidates small files after writes complete

### Benefits
- Reduces small file problem common in streaming workloads
- Improves query performance by reducing number of files to scan
- No manual OPTIMIZE commands needed

### Configuration
Both features are enabled via table properties:
- `delta.autoOptimize.optimizeWrite = true`
- `delta.autoOptimize.autoCompact = true`

## Date-based Partitioning

### Purpose
Partitions data by `_ingestion_date` to enable:
- Efficient time-range queries (e.g., "last 7 days")
- Partition pruning to skip irrelevant data
- Cost savings by scanning less data

### Partition Column
- `_ingestion_date`: Date extracted from `_ingested_at` timestamp in format `yyyy-MM-dd`

### Usage
```sql
-- Query specific date partition
SELECT * FROM bronze_trips
WHERE _ingestion_date = '2026-01-12';

-- Query date range (partition pruning applied)
SELECT * FROM bronze_trips
WHERE _ingestion_date BETWEEN '2026-01-12' AND '2026-01-13';
```

## Enabling Features on Existing Tables

Use the `enable_delta_features.py` script to enable features on all Bronze tables:

```bash
cd data-platform/bronze/scripts
python3 enable_delta_features.py
```

The script will:
1. Enable Change Data Feed on each table
2. Enable auto-optimize and auto-compact
3. Verify properties were set correctly

## Verification

Check that features are enabled using SQL:

```sql
-- Show all table properties
SHOW TBLPROPERTIES delta.`s3a://rideshare-bronze/bronze_trips/`;

-- Check specific properties
SELECT
  key,
  value
FROM (SHOW TBLPROPERTIES delta.`s3a://rideshare-bronze/bronze_trips/`)
WHERE key IN (
  'delta.enableChangeDataFeed',
  'delta.autoOptimize.optimizeWrite',
  'delta.autoOptimize.autoCompact'
);
```

## Performance Impact

### Write Performance
- Slight increase in write latency due to file optimization
- Offset by improved query performance downstream

### Storage
- Auto-compact reduces number of small files
- Better compression with larger files

### Queries
- Significant improvement in query performance
- Partition pruning reduces data scanned by 90%+ for date-range queries

## References

- [Delta Lake Change Data Feed](https://docs.delta.io/latest/delta-change-data-feed.html)
- [Delta Lake Auto Optimize](https://docs.delta.io/latest/optimizations-oss.html#auto-optimize)
- [Delta Lake Partitioning Best Practices](https://docs.delta.io/latest/best-practices.html#partition-data)
