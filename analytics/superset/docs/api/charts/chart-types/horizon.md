# Horizon Chart (`horizon`)

## Description

The Horizon Chart is a time-series visualization that displays how a metric changes over time across different groups. Each group is mapped to its own horizontal row, where change over time is visualized using bar lengths and color intensity. This space-efficient chart type uses layered, mirrored area charts with a shared baseline, allowing you to compare multiple time series in a compact vertical space.

The visualization technique divides the Y-axis into colored bands representing different value ranges. Positive values are shown in one color scheme (typically blues or greens), while negative values use another (typically reds or oranges). By layering these bands and using color intensity to encode magnitude, horizon charts can display many time series in a fraction of the space required by traditional line charts.

## When to Use

Use horizon charts when you need to compare trends across many time series simultaneously in limited vertical space. They are particularly effective when you have 5 or more time series to compare and want to identify patterns, outliers, and correlations across groups. The compact design makes them ideal for dashboards where space is at a premium but detailed trend comparison is essential.

## Example Use Cases

- Monitoring server performance metrics (CPU, memory, network) across dozens of servers in a single view
- Comparing daily sales trends across multiple store locations or product categories over time
- Analyzing stock price movements for a portfolio of securities with limited screen space
- Tracking website traffic patterns across different geographic regions or marketing channels
- Visualizing temperature or weather data trends across multiple weather stations
- Monitoring application error rates or response times across multiple services or endpoints

## Request Format

### Common Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `horizon` |
| datasource_id | integer | Yes | ID of the datasource |
| datasource_type | string | Yes | Type of datasource (e.g., 'table') |
| params | string | Yes | JSON string containing chart-specific parameters |
| description | string | No | Chart description |
| owners | array | No | List of owner user IDs |
| cache_timeout | integer | No | Cache timeout in seconds |
| dashboards | array | No | List of dashboard IDs to add chart to |
| certified_by | string | No | Name of certifier |
| certification_details | string | No | Certification details |

### params Object

The `params` field must be a JSON string containing the following chart-specific parameters:

#### Time Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| granularity_sqla | string | Yes | null | Name of the temporal column used for time filtering and grouping from the datasource. This defines the time dimension for the X-axis. |
| time_range | string | No | 'No filter' | Time range filter for the data. Supports relative ranges like 'Last week', 'Last 30 days', or absolute ISO 8601 format like '2024-01-01 : 2024-12-31'. |

#### Query Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| metrics | array | Yes | [] | List of metrics to display. Can be metric names (strings) or adhoc metric objects. Multiple metrics create separate visualizations. |
| adhoc_filters | array | No | [] | List of adhoc filter objects to apply to the query. Each filter can target specific columns with various operators. |
| groupby | array | No | [] | List of dimension columns to group by. Each unique combination creates a separate row/series in the horizon chart. This is what creates the different horizontal bands. |
| limit | integer | No | null | Maximum number of series/rows to display. Limits the number of groups shown based on the timeseries_limit_metric ranking. |
| timeseries_limit_metric | object/string | No | null | Metric used to rank and limit series when `limit` is specified. Series are sorted by this metric to determine which to include. |
| order_desc | boolean | No | true | Whether to order series in descending order when applying the limit. |
| contribution | boolean | No | false | When enabled, computes each series' contribution to the total as a percentage rather than showing raw values. |
| row_limit | integer | No | 10000 | Maximum number of rows to retrieve from the datasource before aggregation. |

#### Chart Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| series_height | string | No | '25' | Pixel height of each series/row in the chart. Controls how much vertical space each time series occupies. Valid options: '10', '25', '40', '50', '75', '100', '150', '200', or custom numeric value as string. |
| horizon_color_scale | string | No | 'series' | Determines how the value domain is calculated for color encoding. Options: <br/>- **'series'**: Each series is scaled independently based on its own min/max values <br/>- **'overall'**: All series use the same global scale based on overall min/max across all data <br/>- **'change'**: Shows changes compared to the first data point in each series (useful for relative comparison) |

### Metric Object Format

Metrics can be specified as either simple strings (for saved metrics) or adhoc metric objects:

**Simple string format** (for saved metrics):
```json
"COUNT(*)"
```

**Adhoc metric object** (for custom aggregations):
```json
{
  "expressionType": "SIMPLE",
  "column": {
    "column_name": "revenue",
    "type": "DOUBLE"
  },
  "aggregate": "SUM",
  "label": "Total Revenue"
}
```

**SQL expression metric**:
```json
{
  "expressionType": "SQL",
  "sqlExpression": "AVG(response_time_ms)",
  "label": "Avg Response Time"
}
```

### Filter Object Format

Adhoc filters follow this structure:

```json
{
  "clause": "WHERE",
  "subject": "status",
  "operator": "==",
  "comparator": "active",
  "expressionType": "SIMPLE"
}
```

For temporal filters:
```json
{
  "clause": "WHERE",
  "subject": "order_date",
  "operator": "TEMPORAL_RANGE",
  "comparator": "Last quarter",
  "expressionType": "SIMPLE"
}
```

### Example Request

```json
{
  "slice_name": "Server CPU Usage by Region",
  "viz_type": "horizon",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"granularity_sqla\": \"timestamp\", \"time_range\": \"Last 7 days\", \"metrics\": [{\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"cpu_usage\", \"type\": \"DOUBLE\"}, \"aggregate\": \"AVG\", \"label\": \"Avg CPU %\"}], \"groupby\": [\"server_region\", \"server_name\"], \"adhoc_filters\": [{\"clause\": \"WHERE\", \"subject\": \"environment\", \"operator\": \"==\", \"comparator\": \"production\", \"expressionType\": \"SIMPLE\"}], \"series_height\": \"40\", \"horizon_color_scale\": \"overall\", \"limit\": 20, \"timeseries_limit_metric\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"cpu_usage\", \"type\": \"DOUBLE\"}, \"aggregate\": \"AVG\", \"label\": \"Avg CPU %\"}, \"order_desc\": true, \"contribution\": false, \"row_limit\": 10000}",
  "description": "Horizon chart showing CPU usage trends across production servers grouped by region",
  "owners": [1],
  "dashboards": [5]
}
```

### Example Request (Minimal)

```json
{
  "slice_name": "Daily Sales by Store",
  "viz_type": "horizon",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"granularity_sqla\": \"sale_date\", \"metrics\": [\"total_sales\"], \"groupby\": [\"store_name\"]}"
}
```

### Example Request (Contribution Mode)

```json
{
  "slice_name": "Market Share by Product Category",
  "viz_type": "horizon",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"granularity_sqla\": \"date\", \"time_range\": \"Last year\", \"metrics\": [\"revenue\"], \"groupby\": [\"product_category\"], \"contribution\": true, \"series_height\": \"50\", \"horizon_color_scale\": \"series\", \"limit\": 10, \"timeseries_limit_metric\": \"revenue\", \"order_desc\": true}",
  "description": "Product category revenue contribution over time showing market share trends"
}
```

## Response Format

The chart creation endpoint returns a response containing the created chart's details:

```json
{
  "id": 123,
  "slice_name": "Server CPU Usage by Region",
  "viz_type": "horizon",
  "datasource_id": 1,
  "datasource_type": "table",
  "description": "Horizon chart showing CPU usage trends across production servers grouped by region",
  "cache_timeout": null,
  "owners": [1],
  "dashboards": [5]
}
```

## Notes

- **Legacy Chart Type**: This chart is marked as **Legacy** and uses an older D3-based implementation (d3-horizon-chart library). Consider using modern time-series chart types for new implementations.
- **Groupby Creates Series**: The `groupby` parameter is essential for horizon charts. Each unique combination of groupby values creates a separate horizontal row/series in the visualization.
- **Series Height**: Lower heights (10-25px) allow more series to fit on screen but may reduce readability. Higher heights (75-150px) provide better detail but require more vertical space.
- **Color Scale Modes**:
  - Use **'series'** when comparing relative trends within each series (default, most common)
  - Use **'overall'** when comparing absolute magnitudes across all series
  - Use **'change'** when focusing on relative changes from a baseline
- **Limiting Series**: When dealing with high-cardinality groupby columns, use `limit` with `timeseries_limit_metric` to show only the top N series by a specific metric.
- **Contribution Mode**: Setting `contribution: true` converts raw values to percentages of the total, useful for understanding each series' relative contribution over time.
- **Data Requirements**: Requires a temporal column for `granularity_sqla` and at least one metric. Works best with regular time intervals.
- **Space Efficiency**: Horizon charts can display 3-5 times as many time series in the same vertical space compared to traditional line charts, making them ideal for monitoring dashboards with many metrics.
