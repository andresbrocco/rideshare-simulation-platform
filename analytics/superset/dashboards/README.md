# Superset Dashboards

This directory contains exported Superset dashboards for version control and deployment automation.

## Operations Dashboard

The Operations Dashboard (`operations-dashboard.json`) provides real-time monitoring of the rideshare simulation platform with the following components:

### Dashboard Components

#### Trip Metrics (Top Row)
- **Active Trips**: Current count of trips in progress
- **Completed Today**: Total trips completed today with trend indicator
- **Average Wait Time Today**: Average time between request and pickup
- **Total Revenue Today**: Sum of all fares collected today

#### DLQ Error Monitoring (Second Row)
- **DLQ Errors Last Hour**: Time series bar chart showing error volume over time
- **Total DLQ Errors**: Pie chart breaking down errors by type

#### Pipeline Health (Third Row)
- **Hourly Trip Volume**: Line chart showing trip throughput over last 24 hours
- **Pipeline Lag**: Current delay between event generation and processing

#### Zone Visualization (Bottom Row)
- **Trips by Zone Today**: Deck.gl polygon map showing geographic distribution

### Configuration

- **Refresh Interval**: 300 seconds (5 minutes)
- **Database**: Rideshare Gold Layer (Spark Thrift Server)
- **Slug**: `operations`
- **URL**: http://localhost:8088/superset/dashboard/operations/

### Deployment

The dashboard is created programmatically via the Superset API using the scripts in this directory:

1. `setup_database_connection.py` - Creates database connection to Gold layer
2. `create_operations_dashboard_v2.py` - Creates dashboard with all charts
3. `associate_charts.py` - Associates charts with dashboard

To recreate the dashboard:

```bash
cd analytics/superset/dashboards
python3 setup_database_connection.py
python3 create_operations_dashboard_v2.py
python3 associate_charts.py
```

### Testing

Tests are located in `analytics/superset/tests/test_operations_dashboard.py` and verify:

1. Dashboard exists and is accessible via API
2. All 9 required charts are present
3. Auto-refresh interval is configured
4. Dashboard URL returns valid data

Run tests with:

```bash
cd analytics/superset/tests
./venv/bin/pytest test_operations_dashboard.py -v
```

### Notes

- Dashboard uses virtual datasets with SQL queries
- For development, uses PostgreSQL connection instead of Spark Thrift Server
- Production deployment should update connection to use Spark Thrift Server with actual Gold layer tables
- Dashboard export includes all chart definitions and layout configuration
