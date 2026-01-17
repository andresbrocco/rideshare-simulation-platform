# Superset Dashboards

This directory contains exported Superset dashboards for version control and deployment automation.

## Dashboard Overview

All dashboards use virtual datasets with SQL queries and are configured with 5-minute auto-refresh intervals.

| Dashboard | Slug | Charts | Purpose |
|-----------|------|--------|---------|
| Operations Dashboard | `operations` | 9 | Real-time platform monitoring |
| Driver Performance Dashboard | `driver-performance` | 6 | Driver metrics and analytics |
| Demand Analysis Dashboard | `demand-analysis` | 6 | Zone demand and surge patterns |
| Revenue Analytics Dashboard | `revenue-analytics` | 9 | Revenue metrics and KPIs |

## Operations Dashboard

**File**: `operations.json`
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

**File**: `driver-performance.json`
**URL**: http://localhost:8088/superset/dashboard/driver-performance/

### Charts (6 total)

1. **Top 10 Drivers by Trips** - Bar chart of top performers
2. **Driver Ratings Distribution** - Histogram of rating distribution
3. **Driver Payouts Over Time** - Time series line chart
4. **Driver Utilization Heatmap** - Utilization by driver and date
5. **Trips per Driver** - Scatter plot of trips vs revenue
6. **Driver Status Summary** - Pie chart of driver status

## Demand Analysis Dashboard

**File**: `demand-analysis.json`
**URL**: http://localhost:8088/superset/dashboard/demand-analysis/

### Charts (6 total)

1. **Zone Demand Heatmap** - Demand by zone and date
2. **Surge Multiplier Trends** - Time series of surge pricing
3. **Average Wait Time by Zone** - Bar chart by zone
4. **Demand by Hour of Day** - Area chart showing hourly patterns
5. **Top Demand Zones** - Table of highest demand zones
6. **Surge Events Timeline** - Time series bar chart of surge events

## Revenue Analytics Dashboard

**File**: `revenue-analytics.json`
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

# Prerequisites
python3 setup_database_connection.py

# Create individual dashboards
./venv/bin/python3 create_operations_dashboard_v2.py
./venv/bin/python3 create_driver_performance_dashboard.py
./venv/bin/python3 create_demand_analysis_dashboard.py
./venv/bin/python3 create_revenue_analytics_dashboard.py
```

## Exporting Dashboards

To export all dashboards to JSON for version control:

```bash
bash analytics/superset/scripts/export-dashboards.sh
```

This exports all 4 dashboards to JSON files in this directory.

## Testing

Comprehensive test suite covers all dashboards:

```bash
cd analytics/superset/tests
./venv/bin/pytest test_all_dashboards.py -v
```

Tests verify:
- All 4 dashboards exist with correct slugs
- Each dashboard has expected chart count
- Exported JSON files are valid
- Dashboard filters work correctly
- All charts query successfully
- Dashboards are accessible via API

## Configuration

- **Database**: Rideshare Gold Layer (PostgreSQL in dev, Spark Thrift Server in prod)
- **Refresh Interval**: 300 seconds (5 minutes)
- **Datasets**: Virtual datasets using SQL queries
- **Development**: Uses mock data queries for testing
- **Production**: Update SQL queries to reference actual Gold layer tables

## Notes

- Dashboard exports are ZIP files containing full dashboard configuration
- JSON exports include all chart definitions and layout
- Virtual datasets enable dashboard creation without requiring physical tables
- Production deployment should update SQL queries to use actual Spark tables
