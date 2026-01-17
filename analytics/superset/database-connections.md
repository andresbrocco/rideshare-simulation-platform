# Superset Database Connections

This document describes how to configure database connections in Apache Superset to access the Rideshare Gold Layer.

## Spark Thrift Server Connection

Superset connects to the Spark Thrift Server to query Gold layer tables stored in Delta Lake format on MinIO.

### Prerequisites

- Superset running with PyHive driver installed
- Spark Thrift Server running on port 10000
- Gold layer tables created by DBT transformations

### Connection Details

**Display Name**: Rideshare Gold Layer

**Database Type**: Apache Hive

**SQLAlchemy URI**: `hive://hive@spark-thrift-server:10000/default`

### Configuration Steps

1. Log in to Superset at http://localhost:8088 (admin/admin)
2. Navigate to **Data > Databases**
3. Click **+ Database**
4. Select **Apache Hive** from the list
5. Enter connection details:
   - **Display Name**: Rideshare Gold Layer
   - **SQLAlchemy URI**: `hive://hive@spark-thrift-server:10000/default`
6. Click **Advanced** tab and configure:
   - **Allow CREATE TABLE AS**: Yes
   - **Allow CREATE VIEW AS**: Yes
   - **Allow DML**: No (read-only access)
   - **Cache timeout**: 300 seconds
   - **Async query execution**: No
7. Click **Test Connection** - should show "Connection looks good!"
8. Click **Connect** to save

### Testing the Connection

After adding the database connection, test it using SQL Lab:

1. Navigate to **SQL Lab > SQL Editor**
2. Select **Rideshare Gold Layer** from the database dropdown
3. Select **gold** schema
4. Run test queries:

```sql
-- Count trips in fact table
SELECT COUNT(*) FROM gold.fact_trips;

-- View recent trips
SELECT trip_id, pickup_time, dropoff_time, total_fare
FROM gold.fact_trips
ORDER BY pickup_time DESC
LIMIT 10;

-- Check dimension tables
SELECT COUNT(*) FROM gold.dim_drivers;
SELECT COUNT(*) FROM gold.dim_riders;
SELECT COUNT(*) FROM gold.dim_zones;
```

### Registering Datasets

To create dashboards, register Gold layer tables as datasets:

1. Navigate to **Data > Datasets**
2. Click **+ Dataset**
3. Select configuration:
   - **Database**: Rideshare Gold Layer
   - **Schema**: gold
   - **Table**: fact_trips (or other table)
4. Click **Add** to register the dataset
5. Repeat for other tables as needed

### Available Tables

Gold layer contains the following tables:

**Fact Tables:**
- `gold.fact_trips` - Trip-level facts with foreign keys to dimensions
- `gold.fact_gps_pings` - GPS location events aggregated by trip segment

**Dimension Tables:**
- `gold.dim_drivers` - SCD Type 2 driver dimension
- `gold.dim_riders` - SCD Type 2 rider dimension
- `gold.dim_zones` - Zone geographic and demographic attributes
- `gold.dim_time` - Time dimension for temporal analysis

**Aggregate Tables:**
- `gold.agg_hourly_zone_metrics` - Hourly aggregates by zone
- `gold.agg_daily_driver_metrics` - Daily driver performance metrics

### Troubleshooting

**Connection fails:**
- Verify Spark Thrift Server is running: `docker compose ps spark-thrift-server`
- Check Thrift Server logs: `docker compose logs spark-thrift-server`
- Ensure both services are on the same Docker network

**Tables not visible:**
- Verify Gold layer tables exist by connecting via beeline or spark-sql
- Check schema name is correct (should be `gold`, not `default`)
- Refresh schema cache in Superset

**Query timeout:**
- Increase cache timeout in database settings
- Consider enabling async query execution for long-running queries
- Check Spark cluster resources and tune executor memory

### Connection String Format

The connection string follows the PyHive SQLAlchemy format:

```
hive://[username]@[hostname]:[port]/[database]
```

For our setup:
- **username**: `hive` (default, authentication not enforced)
- **hostname**: `spark-thrift-server` (Docker service name)
- **port**: `10000` (Spark Thrift Server default)
- **database**: `default` (Spark default database)

Note: Tables are accessed via schema qualifier (e.g., `gold.fact_trips`) rather than database name.

### Security Notes

This is a development configuration with no authentication (NOSASL mode). Production deployments should:

- Enable Kerberos authentication on Spark Thrift Server
- Use SSL/TLS for encrypted connections
- Implement row-level security in Superset
- Configure database-specific roles and permissions
- Audit query access logs
