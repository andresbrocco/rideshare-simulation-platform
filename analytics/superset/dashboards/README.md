# Superset Dashboards

This directory contains dashboard creation scripts, SQL query libraries, and exported dashboard files for the Rideshare Lakehouse.

## Dashboard Overview

All dashboards use virtual datasets with SQL queries and are configured with 5-minute auto-refresh intervals.

| Dashboard | Slug | Charts | Layer | Purpose |
|-----------|------|--------|-------|---------|
| Operations Dashboard | `operations` | 9 | Gold | Real-time platform monitoring |
| Driver Performance Dashboard | `driver-performance` | 6 | Gold | Driver metrics and analytics |
| Demand Analysis Dashboard | `demand-analysis` | 6 | Gold | Zone demand and surge patterns |
| Revenue Analytics Dashboard | `revenue-analytics` | 9 | Gold | Revenue metrics and KPIs |
| Bronze Pipeline Dashboard | `bronze-pipeline` | 8 | Bronze | Ingestion metrics and DLQ monitoring |
| Silver Quality Dashboard | `silver-quality` | 8 | Silver | Anomaly detection and data freshness |

**Total: 6 dashboards, 46 charts**

## Query Libraries

SQL queries are centralized in three Python modules:

| Module | Layer | Queries | Description |
|--------|-------|---------|-------------|
| `bronze_queries.py` | Bronze | 8 | Ingestion metrics, DLQ errors, Kafka partitions |
| `silver_queries.py` | Silver | 8 | Anomalies, staging tables, data freshness |
| `gold_queries.py` | Gold | 30 | Facts, dimensions, aggregates for 4 dashboards |

### Bronze Layer Queries

| Query | Description |
|-------|-------------|
| `TOTAL_EVENTS_24H` | Total events ingested across all topics |
| `EVENTS_BY_TOPIC` | Event distribution by Kafka topic |
| `INGESTION_RATE_HOURLY` | Hourly ingestion rate time series |
| `DLQ_ERROR_COUNT` | Dead letter queue error count |
| `DLQ_ERRORS_BY_TYPE` | DLQ errors grouped by error type |
| `PARTITION_DISTRIBUTION` | Events per Kafka partition |
| `LATEST_INGESTION` | Latest ingestion timestamp per topic |
| `INGESTION_LAG` | Max lag between event and ingestion time |

### Silver Layer Queries

| Query | Description |
|-------|-------------|
| `TOTAL_ANOMALIES` | Total anomalies detected (24h) |
| `ANOMALIES_BY_TYPE` | Anomaly distribution by type |
| `ANOMALIES_OVER_TIME` | Hourly anomaly trend |
| `GPS_OUTLIERS_COUNT` | GPS coordinates outside São Paulo bounds |
| `IMPOSSIBLE_SPEEDS_COUNT` | Speeds exceeding 200 km/h |
| `ZOMBIE_DRIVERS_LIST` | Drivers with no GPS for 10+ minutes |
| `STAGING_ROW_COUNTS` | Row counts per staging table |
| `STAGING_FRESHNESS` | Latest ingestion per staging table |

### Gold Layer Queries

Organized by dashboard:

- **OPERATIONS_QUERIES** (9): Active trips, completed today, wait time, revenue, DLQ, hourly volume, pipeline lag, zone distribution
- **DRIVER_PERFORMANCE_QUERIES** (6): Top drivers, ratings, payouts, utilization, trips per driver, status summary
- **DEMAND_ANALYSIS_QUERIES** (6): Zone demand, surge trends, wait time by zone, hourly demand, top zones, surge events
- **REVENUE_ANALYTICS_QUERIES** (9): Daily revenue, fees, trip count, zone revenue, revenue over time, fare by distance, payment methods, hourly revenue, top zones

## Bronze Pipeline Dashboard

**URL**: http://localhost:8088/superset/dashboard/bronze-pipeline/

### Charts (8 total)

1. **Total Events (24h)** - Big number showing total ingested events
2. **DLQ Errors** - Dead letter queue error count
3. **Max Ingestion Lag (s)** - Maximum lag between event timestamp and ingestion
4. **Events by Topic** - Bar chart of event distribution across Kafka topics
5. **Partition Distribution** - Bar chart showing events per Kafka partition
6. **Ingestion Rate (Hourly)** - Time series of hourly ingestion rate
7. **DLQ Errors by Type** - Pie chart of error type distribution
8. **Latest Ingestion** - Table showing data freshness per topic

## Silver Quality Dashboard

**URL**: http://localhost:8088/superset/dashboard/silver-quality/

### Charts (8 total)

1. **Total Anomalies (24h)** - Big number showing detected anomalies
2. **GPS Outliers** - Count of GPS coordinates outside bounds
3. **Impossible Speeds** - Count of speeds > 200 km/h
4. **Anomalies by Type** - Pie chart of anomaly type distribution
5. **Anomalies Over Time** - Time series of hourly anomaly count
6. **Staging Row Counts** - Bar chart of rows per staging table
7. **Zombie Drivers** - Table of drivers with stale GPS data
8. **Data Freshness** - Table of latest ingestion per staging table

## Operations Dashboard

**URL**: http://localhost:8088/superset/dashboard/operations/

### Charts (9 total)

1. **Active Trips** - Current trips in progress
2. **Completed Today** - Total completed trips with trend
3. **Average Wait Time Today** - Average wait time metric
4. **Total Revenue Today** - Daily revenue sum
5. **DLQ Errors Last Hour** - Time series error volume
6. **Total DLQ Errors** - Pie chart by error type
7. **Hourly Trip Volume** - 24-hour trip throughput
8. **Pipeline Lag** - Event processing delay
9. **Trips by Zone Today** - Geographic distribution map

## Driver Performance Dashboard

**URL**: http://localhost:8088/superset/dashboard/driver-performance/

### Charts (6 total)

1. **Top 10 Drivers by Trips** - Bar chart of top performers
2. **Driver Ratings Distribution** - Histogram of rating distribution
3. **Driver Payouts Over Time** - Time series line chart
4. **Driver Utilization Heatmap** - Utilization by driver and date
5. **Trips per Driver** - Scatter plot of trips vs revenue
6. **Driver Status Summary** - Pie chart of driver status

## Demand Analysis Dashboard

**URL**: http://localhost:8088/superset/dashboard/demand-analysis/

### Charts (6 total)

1. **Zone Demand Heatmap** - Demand by zone and date
2. **Surge Multiplier Trends** - Time series of surge pricing
3. **Average Wait Time by Zone** - Bar chart by zone
4. **Demand by Hour of Day** - Area chart showing hourly patterns
5. **Top Demand Zones** - Table of highest demand zones
6. **Surge Events Timeline** - Time series bar chart of surge events

## Revenue Analytics Dashboard

**URL**: http://localhost:8088/superset/dashboard/revenue-analytics/

### Charts (9 total)

**KPIs (Top Row)**
1. **Daily Revenue** - Big number with trend indicator
2. **Total Fees** - Big number KPI
3. **Trip Count** - Big number KPI

**Analytics Charts**
4. **Revenue by Zone** - Bar chart showing zone breakdown
5. **Revenue Over Time** - Time series line chart
6. **Average Fare by Distance** - Scatter plot analysis
7. **Payment Method Distribution** - Pie chart
8. **Revenue by Hour** - Heatmap by hour and date
9. **Top Revenue Zones** - Table of highest revenue zones

## Creating Dashboards

All dashboards are created programmatically using Python scripts:

```bash
cd analytics/superset/dashboards

# Prerequisites - ensure Superset is running
docker compose -f infrastructure/docker/compose.yml --profile analytics up -d

# Create Gold layer dashboards
./venv/bin/python3 create_operations_dashboard_v2.py
./venv/bin/python3 create_driver_performance_dashboard.py
./venv/bin/python3 create_demand_analysis_dashboard.py
./venv/bin/python3 create_revenue_analytics_dashboard.py

# Create Bronze/Silver layer dashboards
./venv/bin/python3 create_bronze_pipeline_dashboard.py
./venv/bin/python3 create_silver_quality_dashboard.py
```

## Importing Dashboards

Dashboards can be imported from ZIP exports on container startup:

```bash
# Automatic import on startup (configured in docker-entrypoint.sh)
# Or run manually:
python3 import_dashboards.py --base-url http://localhost:8088

# Force overwrite existing dashboards
python3 import_dashboards.py --base-url http://localhost:8088 --force
```

## Exporting Dashboards

To export all dashboards to JSON for version control:

```bash
bash analytics/superset/scripts/export-dashboards.sh
```

This exports all 6 dashboards to JSON files in this directory.

## Testing

Comprehensive test suite covers all dashboards:

```bash
cd analytics/superset/tests
./venv/bin/pytest test_all_dashboards.py -v
```

Tests verify:
- All 6 dashboards exist with correct slugs
- Each dashboard has expected chart count
- Exported JSON files are valid
- Dashboard filters work correctly
- All charts query successfully
- Dashboards are accessible via API

## Configuration

- **Database**: Rideshare Lakehouse (Spark Thrift Server)
- **Refresh Interval**: 300 seconds (5 minutes)
- **Datasets**: Virtual datasets using SQL queries
- **Tables**: Bronze (bronze.*), Silver (silver.*), Gold (gold.*)

## File Structure

```
dashboards/
├── README.md                              # This file
├── bronze_queries.py                      # Bronze layer SQL queries
├── silver_queries.py                      # Silver layer SQL queries
├── gold_queries.py                        # Gold layer SQL queries
├── import_dashboards.py                   # Dashboard import automation
├── create_bronze_pipeline_dashboard.py   # Bronze dashboard creation
├── create_silver_quality_dashboard.py    # Silver dashboard creation
├── create_operations_dashboard_v2.py     # Operations dashboard creation
├── create_driver_performance_dashboard.py # Driver dashboard creation
├── create_demand_analysis_dashboard.py   # Demand dashboard creation
├── create_revenue_analytics_dashboard.py # Revenue dashboard creation
├── bronze-pipeline.json                   # Exported Bronze dashboard (ZIP)
├── silver-quality.json                    # Exported Silver dashboard (ZIP)
├── operations.json                        # Exported Operations dashboard (ZIP)
├── driver-performance.json                # Exported Driver dashboard (ZIP)
├── demand-analysis.json                   # Exported Demand dashboard (ZIP)
└── revenue-analytics.json                 # Exported Revenue dashboard (ZIP)
```

## Notes

- Dashboard exports are ZIP files containing full dashboard configuration (YAML format)
- Virtual datasets enable dashboard creation without requiring physical tables
- All creation scripts share a common SupersetClient class pattern
- Production deployment should update SQL queries if table names differ
