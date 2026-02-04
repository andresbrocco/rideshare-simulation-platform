# Dataset API Reference

This guide provides comprehensive documentation for managing datasets (also known as "tables" or "datasources") via the Superset REST API. Datasets are the foundation for building charts and dashboards in Superset.

## Overview

A dataset in Superset can be:
- **Physical**: Points to an actual database table or view
- **Virtual**: Defined by a SQL query (also called "SQL-based" datasets)

Datasets contain:
- **Columns**: Physical columns from the table or calculated columns defined by SQL expressions
- **Metrics**: Aggregation expressions (e.g., `SUM(sales)`, `COUNT(*)`)

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/dataset/` | Create a new dataset |
| `GET` | `/api/v1/dataset/` | List all datasets |
| `GET` | `/api/v1/dataset/{pk}` | Get a dataset by ID |
| `PUT` | `/api/v1/dataset/{pk}` | Update a dataset |
| `DELETE` | `/api/v1/dataset/{pk}` | Delete a dataset |
| `PUT` | `/api/v1/dataset/{pk}/refresh` | Refresh dataset columns from database |
| `DELETE` | `/api/v1/dataset/{pk}/column/{column_id}` | Delete a specific column |
| `DELETE` | `/api/v1/dataset/{pk}/metric/{metric_id}` | Delete a specific metric |
| `POST` | `/api/v1/dataset/duplicate` | Duplicate a dataset |
| `POST` | `/api/v1/dataset/get_or_create/` | Get or create a dataset by name |
| `GET` | `/api/v1/dataset/export/` | Export datasets as YAML |
| `POST` | `/api/v1/dataset/import/` | Import datasets from YAML |

---

## Creating a Dataset

### POST /api/v1/dataset/

Creates a new dataset. After creation, columns are automatically fetched from the database.

**Important**: You cannot set columns or metrics during creation. Use `PUT` to configure them after creation.

### Request Body Schema

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `database` | integer | **Yes** | Database connection ID |
| `table_name` | string | **Yes** | Physical table name (1-250 characters) |
| `schema` | string | No | Database schema name (0-250 characters) |
| `catalog` | string | No | Catalog name for multi-catalog databases (0-250 characters) |
| `sql` | string | No | SQL query for virtual datasets |
| `owners` | array[integer] | No | List of owner user IDs |
| `normalize_columns` | boolean | No | Normalize column names (default: `false`) |
| `always_filter_main_dttm` | boolean | No | Always filter on main datetime column (default: `false`) |
| `template_params` | string | No | JSON string of Jinja template parameters |
| `is_managed_externally` | boolean | No | Whether dataset is managed by external system (default: `false`) |
| `external_url` | string | No | URL to external management system |
| `uuid` | string | No | Optional UUID for the dataset |

### Example: Create a Physical Dataset

```bash
curl -X POST "http://localhost:8088/api/v1/dataset/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "database": 1,
    "table_name": "sales_data",
    "schema": "public",
    "owners": [1]
  }'
```

### Example: Create a Virtual (SQL-based) Dataset

```bash
curl -X POST "http://localhost:8088/api/v1/dataset/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "database": 1,
    "table_name": "sales_summary",
    "schema": "public",
    "sql": "SELECT customer_id, SUM(amount) as total_amount, COUNT(*) as order_count FROM orders GROUP BY customer_id",
    "owners": [1]
  }'
```

### Response

```json
{
  "id": 42,
  "result": {
    "id": 42,
    "table_name": "sales_data",
    "schema": "public",
    "database_id": 1
  }
}
```

---

## Updating a Dataset

### PUT /api/v1/dataset/{pk}

Updates an existing dataset. This is where you configure columns, calculated columns, and metrics.

### Request Body Schema

#### Basic Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `database_id` | integer | **Yes** | Database connection ID (note: `database_id`, not `database`) |
| `table_name` | string | No | Physical table name (1-250 characters) |
| `schema` | string | No | Database schema name (0-255 characters) |
| `catalog` | string | No | Catalog name (0-250 characters) |
| `sql` | string | No | SQL query for virtual datasets |
| `description` | string | No | Dataset description |
| `main_dttm_col` | string | No | Name of the main datetime column |
| `default_endpoint` | string | No | Default endpoint URL |
| `cache_timeout` | integer | No | Cache timeout in seconds |
| `offset` | integer | No | SQL query result offset |
| `owners` | array[integer] | No | List of owner user IDs |
| `filter_select_enabled` | boolean | No | Enable filter select on dataset |
| `fetch_values_predicate` | string | No | SQL predicate for filtering values (0-1000 chars) |
| `normalize_columns` | boolean | No | Normalize column names |
| `always_filter_main_dttm` | boolean | No | Always filter on main datetime column |
| `is_sqllab_view` | boolean | No | Whether this is a SQL Lab view |
| `template_params` | string | No | JSON string of Jinja template parameters |
| `extra` | string | No | Additional JSON metadata |
| `is_managed_externally` | boolean | No | External management flag |
| `external_url` | string | No | External management URL |
| `currency_code_column` | string | No | Currency code column name |

#### Columns Array

The `columns` property accepts an array of column objects. Each column can be a physical column (from the database) or a calculated column (defined by a SQL expression).

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | integer | No* | Column ID (required to update existing columns) |
| `column_name` | string | **Yes** | Column name (1-255 characters) |
| `type` | string | No | SQL data type (e.g., `VARCHAR`, `INTEGER`, `TIMESTAMP`) |
| `verbose_name` | string | No | Display name (max 1024 characters) |
| `description` | string | No | Column description |
| `expression` | string | No | SQL expression for calculated columns |
| `filterable` | boolean | **Yes** | Whether column appears in filter options |
| `groupby` | boolean | **Yes** | Whether column can be used for grouping (dimension) |
| `is_dttm` | boolean | No | Whether column is a datetime/temporal column (default: `false`) |
| `python_date_format` | string | No | Python datetime format string (1-255 characters) |
| `datetime_format` | string | No | Datetime format string (1-100 characters) |
| `is_active` | boolean | No | Whether column is active |
| `advanced_data_type` | string | No | Advanced data type (1-255 characters) |
| `extra` | string | No | Additional JSON metadata |
| `uuid` | string | No | Column UUID |

**Note**: Omit `id` to create a new calculated column. Include `id` to update an existing column.

##### Column Property Mapping to UI

| API Property | UI Label | Description |
|--------------|----------|-------------|
| `is_dttm` | "Is Temporal" | Marks column as datetime for time-series charts |
| `python_date_format` | "Datetime Format" | Format for parsing datetime strings |
| `filterable` | "Is Filterable" | Column appears in filter dropdowns |
| `groupby` | "Is Dimension" | Column can be used for GROUP BY operations |
| `expression` | "SQL Expression" | Defines a calculated column |

#### Metrics Array

The `metrics` property accepts an array of metric objects.

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `id` | integer | **Yes** | Metric ID (required for updates) |
| `metric_name` | string | **Yes** | Metric name (1-255 characters) |
| `expression` | string | **Yes** | SQL aggregation expression |
| `verbose_name` | string | No | Display name (max 1024 characters) |
| `description` | string | No | Metric description |
| `metric_type` | string | No | Type of metric (1-32 characters) |
| `d3format` | string | No | D3 format string for display (1-128 characters) |
| `warning_text` | string | No | Warning message shown to users |
| `extra` | string | No | Additional JSON metadata |
| `uuid` | string | No | Metric UUID |
| `currency` | object | No | Currency formatting options |

##### Currency Object

| Property | Type | Description |
|----------|------|-------------|
| `symbol` | string | Currency symbol (e.g., `$`, `€`) |
| `symbolPosition` | string | Position of symbol (`prefix` or `suffix`) |

### Example: Configure Columns and Metrics

```bash
curl -X PUT "http://localhost:8088/api/v1/dataset/42" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "database_id": 1,
    "main_dttm_col": "created_at",
    "columns": [
      {
        "id": 101,
        "column_name": "created_at",
        "type": "TIMESTAMP",
        "is_dttm": true,
        "filterable": true,
        "groupby": true,
        "python_date_format": "%Y-%m-%d %H:%M:%S"
      },
      {
        "id": 102,
        "column_name": "customer_id",
        "type": "INTEGER",
        "filterable": true,
        "groupby": true,
        "verbose_name": "Customer ID"
      },
      {
        "id": 103,
        "column_name": "amount",
        "type": "DECIMAL",
        "filterable": true,
        "groupby": false
      },
      {
        "column_name": "amount_with_tax",
        "expression": "amount * 1.1",
        "type": "DECIMAL",
        "filterable": true,
        "groupby": false,
        "verbose_name": "Amount (with 10% tax)",
        "description": "Calculated column: amount plus 10% tax"
      }
    ],
    "metrics": [
      {
        "metric_name": "total_amount",
        "expression": "SUM(amount)",
        "verbose_name": "Total Amount",
        "description": "Sum of all transaction amounts",
        "d3format": ",.2f"
      },
      {
        "metric_name": "avg_amount",
        "expression": "AVG(amount)",
        "verbose_name": "Average Amount",
        "d3format": ",.2f"
      },
      {
        "metric_name": "transaction_count",
        "expression": "COUNT(*)",
        "verbose_name": "Number of Transactions",
        "d3format": ",d"
      },
      {
        "metric_name": "revenue_usd",
        "expression": "SUM(amount)",
        "verbose_name": "Revenue (USD)",
        "d3format": ",.2f",
        "currency": {
          "symbol": "$",
          "symbolPosition": "prefix"
        }
      }
    ]
  }'
```

### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `override_columns` | boolean | Set to `true` to refresh columns from database and overwrite existing column configuration |

```bash
# Refresh columns from database
curl -X PUT "http://localhost:8088/api/v1/dataset/42?override_columns=true" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"database_id": 1}'
```

---

## Complete Workflow Example

Here's a complete example showing how to create and fully configure a dataset:

### Step 1: Create the Dataset

```bash
# Create a virtual dataset with a SQL query
curl -X POST "http://localhost:8088/api/v1/dataset/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "database": 1,
    "table_name": "monthly_sales_report",
    "schema": "analytics",
    "sql": "SELECT date_trunc('\''month'\'', order_date) as month, product_category, customer_region, SUM(quantity) as total_quantity, SUM(amount) as total_amount, COUNT(DISTINCT customer_id) as unique_customers FROM orders JOIN products ON orders.product_id = products.id JOIN customers ON orders.customer_id = customers.id GROUP BY 1, 2, 3",
    "owners": [1]
  }'

# Response: {"id": 42, ...}
```

### Step 2: Get Column IDs

```bash
# Fetch the dataset to get auto-generated column IDs
curl -X GET "http://localhost:8088/api/v1/dataset/42" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Step 3: Configure Columns and Add Metrics

```bash
curl -X PUT "http://localhost:8088/api/v1/dataset/42" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "database_id": 1,
    "description": "Monthly aggregated sales data by product category and customer region",
    "main_dttm_col": "month",
    "columns": [
      {
        "id": 201,
        "column_name": "month",
        "is_dttm": true,
        "filterable": true,
        "groupby": true,
        "verbose_name": "Month",
        "python_date_format": "%Y-%m-%d"
      },
      {
        "id": 202,
        "column_name": "product_category",
        "filterable": true,
        "groupby": true,
        "verbose_name": "Product Category"
      },
      {
        "id": 203,
        "column_name": "customer_region",
        "filterable": true,
        "groupby": true,
        "verbose_name": "Customer Region"
      },
      {
        "id": 204,
        "column_name": "total_quantity",
        "filterable": true,
        "groupby": false
      },
      {
        "id": 205,
        "column_name": "total_amount",
        "filterable": true,
        "groupby": false
      },
      {
        "id": 206,
        "column_name": "unique_customers",
        "filterable": true,
        "groupby": false
      },
      {
        "column_name": "avg_order_value",
        "expression": "total_amount / NULLIF(unique_customers, 0)",
        "type": "DECIMAL",
        "filterable": false,
        "groupby": false,
        "verbose_name": "Average Order Value",
        "description": "Total amount divided by unique customers"
      }
    ],
    "metrics": [
      {
        "metric_name": "sum_quantity",
        "expression": "SUM(total_quantity)",
        "verbose_name": "Total Units Sold",
        "d3format": ",d"
      },
      {
        "metric_name": "sum_amount",
        "expression": "SUM(total_amount)",
        "verbose_name": "Total Revenue",
        "d3format": "$,.2f"
      },
      {
        "metric_name": "sum_customers",
        "expression": "SUM(unique_customers)",
        "verbose_name": "Total Unique Customers",
        "d3format": ",d"
      },
      {
        "metric_name": "avg_revenue_per_customer",
        "expression": "SUM(total_amount) / NULLIF(SUM(unique_customers), 0)",
        "verbose_name": "Avg Revenue per Customer",
        "d3format": "$,.2f"
      }
    ]
  }'
```

---

## Additional Operations

### Refresh Dataset Columns

Re-sync columns from the database schema:

```bash
curl -X PUT "http://localhost:8088/api/v1/dataset/42/refresh" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Delete a Column

```bash
curl -X DELETE "http://localhost:8088/api/v1/dataset/42/column/101" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Delete a Metric

```bash
curl -X DELETE "http://localhost:8088/api/v1/dataset/42/metric/501" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Duplicate a Dataset

```bash
curl -X POST "http://localhost:8088/api/v1/dataset/duplicate" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "base_model_id": 42,
    "table_name": "monthly_sales_report_copy"
  }'
```

### Get or Create Dataset

Retrieves a dataset by name, or creates it if it doesn't exist:

```bash
curl -X POST "http://localhost:8088/api/v1/dataset/get_or_create/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "database_id": 1,
    "table_name": "sales_data",
    "schema": "public"
  }'
```

### Export Datasets

```bash
# Export specific datasets
curl -X GET "http://localhost:8088/api/v1/dataset/export/?q=(ids:!(42,43))" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -o datasets.zip
```

### Import Datasets

```bash
curl -X POST "http://localhost:8088/api/v1/dataset/import/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "formData=@datasets.zip" \
  -F "overwrite=true"
```

---

## Using Jinja Templates

Datasets support Jinja templating for dynamic SQL. Set template parameters as a JSON string:

```bash
curl -X PUT "http://localhost:8088/api/v1/dataset/42" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "database_id": 1,
    "sql": "SELECT * FROM orders WHERE region = '\''{{ region }}'\'' AND order_date >= '\''{{ start_date }}'\''",
    "template_params": "{\"region\": \"US\", \"start_date\": \"2024-01-01\"}"
  }'
```

---

## Folders (Organizing Columns and Metrics)

When the `DATASET_FOLDERS` feature flag is enabled, you can organize columns and metrics into folders:

```bash
curl -X PUT "http://localhost:8088/api/v1/dataset/42" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "database_id": 1,
    "folders": [
      {
        "uuid": "folder-uuid-1",
        "name": "Date Fields",
        "description": "All date and time related columns",
        "children": [
          {"uuid": "column-uuid-created-at", "type": "column"},
          {"uuid": "column-uuid-updated-at", "type": "column"}
        ]
      },
      {
        "uuid": "folder-uuid-2",
        "name": "Revenue Metrics",
        "description": "Financial metrics",
        "children": [
          {"uuid": "metric-uuid-total-revenue", "type": "metric"},
          {"uuid": "metric-uuid-avg-revenue", "type": "metric"}
        ]
      }
    ]
  }'
```

---

## Error Responses

| Status Code | Description |
|-------------|-------------|
| `400` | Bad request - Invalid parameters or validation error |
| `401` | Unauthorized - Missing or invalid authentication |
| `403` | Forbidden - Insufficient permissions |
| `404` | Not found - Dataset doesn't exist |
| `409` | Conflict - Dataset with same name already exists |
| `422` | Unprocessable Entity - Semantic validation error |
| `500` | Internal server error |

### Common Validation Errors

- **Duplicate column names**: Each column must have a unique `column_name`
- **Duplicate metric names**: Each metric must have a unique `metric_name`
- **Invalid column ID**: When updating, the `id` must reference an existing column
- **Invalid metric ID**: When updating, the `id` must reference an existing metric
- **Table already exists**: The combination of `(database_id, catalog, schema, table_name)` must be unique

---

## API Differences: POST vs PUT

| Feature | POST (Create) | PUT (Update) |
|---------|---------------|--------------|
| Database parameter name | `database` | `database_id` |
| Set columns | No | Yes |
| Set metrics | No | Yes |
| Set folders | No | Yes |
| Auto-fetch metadata | Yes (automatic) | Only with `?override_columns=true` |

---

## Best Practices

1. **Always use PUT for column/metric configuration**: The POST endpoint only creates the dataset; use PUT to configure columns and metrics.

2. **Get column IDs before updating**: Fetch the dataset first to get the auto-generated column IDs, then include those IDs when updating columns.

3. **Use calculated columns for derived values**: Instead of creating complex SQL in your virtual dataset, use calculated columns with the `expression` field.

4. **Set appropriate column properties**:
   - Mark datetime columns with `is_dttm: true`
   - Set `filterable: true` for columns users should filter on
   - Set `groupby: true` for dimension columns (categories, IDs)
   - Set `groupby: false` for measure columns (amounts, counts)

5. **Use descriptive names**: Set `verbose_name` and `description` for better discoverability in the UI.

6. **Leverage D3 formats for metrics**: Use `d3format` to control how metric values are displayed (e.g., `",.2f"` for numbers with commas and 2 decimal places).

---

## Related Documentation

- [Chart Types API Reference](../chart-types/_index.md) - Creating charts that use datasets
- [Database API](../../docs/api.mdx) - Managing database connections
- [SQL Templating](../../docs/configuration/sql-templating.mdx) - Jinja templating in SQL
