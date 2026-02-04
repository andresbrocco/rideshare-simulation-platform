# World Map (`world_map`)

## Description

A map of the world that can indicate values in different countries. This visualization uses choropleth coloring to represent metric values across countries and optionally displays bubbles on top of countries to show additional metrics. The World Map chart is built on [Datamaps](http://datamaps.github.io/) and is part of Superset's legacy chart plugins.

## When to Use

Use the World Map chart when you need to:

- Visualize geographic data at the country level
- Compare metric values across different countries using color intensity
- Show multiple metrics per country (using both country color and bubble size)
- Create interactive geographic visualizations with drill-down capabilities

## Example Use Cases

- **Sales Performance by Country**: Display revenue by country using color intensity, with bubble size representing number of customers
- **Population Metrics**: Show population density with color shading and GDP as bubble size
- **Supply Chain Analysis**: Visualize supplier locations and order volumes across countries
- **COVID-19 Tracking**: Display case counts or vaccination rates by country
- **Customer Distribution**: Show customer concentration across countries with additional revenue metrics

## Common Fields

These fields are common to all chart types in Superset.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `slice_name` | string | Yes | The name of the chart (1-250 characters) |
| `description` | string | No | A description of the chart's purpose |
| `viz_type` | string | Yes | Must be `"world_map"` for this chart type |
| `datasource_id` | integer | Yes | The ID of the dataset/datasource |
| `datasource_type` | string | Yes | The type of datasource (`"table"` or `"query"`) |
| `dashboards` | array[integer] | No | List of dashboard IDs to add this chart to |
| `owners` | array[integer] | No | List of user IDs who can modify this chart |
| `params` | string (JSON) | No | JSON string containing chart configuration (see params Object below) |
| `query_context` | string (JSON) | No | The query context for data fetching |
| `cache_timeout` | integer | No | Duration in seconds for caching this chart |
| `certified_by` | string | No | Person or group that certified this chart |
| `certification_details` | string | No | Details about the certification |

## params Object

The `params` field is a JSON string containing the chart configuration. Below are the fields specific to the World Map chart type.

### Query Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `entity` | string or object | Yes | - | The column containing country identifiers. Can be a column name string or an adhoc column object |
| `country_fieldtype` | string | No | `"cca2"` | The country code standard format. Options: `"name"` (full name), `"cioc"` (International Olympic Committee code), `"cca2"` (ISO 3166-1 alpha-2), `"cca3"` (ISO 3166-1 alpha-3) |
| `metric` | string or object | Yes | - | The primary metric to aggregate and display. Can be a saved metric name or an adhoc metric object |
| `adhoc_filters` | array[object] | No | `[]` | List of filters to apply to the data |
| `row_limit` | integer | No | `10000` | Maximum number of rows to fetch from the datasource (0-50000) |
| `sort_by_metric` | boolean | No | `false` | Whether to sort results by the selected metric in descending order |

### Visualization Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `show_bubbles` | boolean | No | `false` | Whether to display bubbles on top of countries |
| `secondary_metric` | string or object | No | `null` | The metric used to determine bubble size. Only relevant when `show_bubbles` is `true` |
| `max_bubble_size` | string or integer | No | `"25"` | Maximum size of bubbles in pixels. Common values: `"5"`, `"10"`, `"15"`, `"25"`, `"50"`, `"75"`, `"100"` |
| `color_picker` | object | No | `{"r": 0, "g": 122, "b": 135, "a": 1}` | RGB color for bubbles. Format: `{"r": 0-255, "g": 0-255, "b": 0-255, "a": 0-1}` |
| `color_by` | string | No | `"metric"` | Determines country coloring method. Options: `"metric"` (shade by metric value), `"country"` (categorical colors) |
| `linear_color_scheme` | string | No | `"blue_white_yellow"` | Color scheme for countries when `color_by` is `"metric"`. Uses sequential color palettes |
| `color_scheme` | string | No | `"supersetColors"` | Color scheme for countries when `color_by` is `"country"`. Uses categorical color palettes |

### Chart Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `y_axis_format` | string | No | `"SMART_NUMBER"` | D3 format string for metric values. Examples: `".3s"` (SI prefix), `",.2f"` (thousands separator with 2 decimals), `".1%"` (percentage) |
| `currency_format` | object | No | `null` | Currency formatting configuration. Can specify currency symbol and position |

### Advanced Metric Configuration

Adhoc metrics allow you to define custom aggregations without saving them to the datasource. An adhoc metric object has the following structure:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `expressionType` | string | Yes | Either `"SIMPLE"` or `"SQL"` |
| `aggregate` | string | Conditional | Aggregation function. Required for `"SIMPLE"` type. Options: `"AVG"`, `"COUNT"`, `"COUNT_DISTINCT"`, `"MAX"`, `"MIN"`, `"SUM"` |
| `column` | object | Conditional | Column definition object. Required for `"SIMPLE"` type |
| `sqlExpression` | string | Conditional | SQL expression for the metric. Required for `"SQL"` type |
| `label` | string | No | Display label for the metric |
| `hasCustomLabel` | boolean | No | Whether a custom label is provided |
| `optionName` | string | No | Unique identifier for the metric |

### Advanced Filter Configuration

Adhoc filters allow you to filter data dynamically. A filter object has the following structure:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `col` | string or object | Yes | The column to filter by (column name or adhoc column object) |
| `op` | string | Yes | Comparison operator. Options: `"IN"`, `"NOT IN"`, `"=="`, `"!="`, `">"`, `"<"`, `">="`, `"<="`, `"LIKE"`, `"ILIKE"`, `"IS NULL"`, `"IS NOT NULL"` |
| `val` | any | Conditional | The value(s) to compare against. Can be string, number, array, or null depending on operator |
| `grain` | string | No | Optional time grain for temporal filters (e.g., `"PT1M"` for 1 minute) |
| `isExtra` | boolean | No | Whether the filter was added by a filter component |

## Example Request JSON

### Basic World Map with Country Shading

```json
{
  "slice_name": "Sales by Country",
  "viz_type": "world_map",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"entity\":\"country_code\",\"country_fieldtype\":\"cca2\",\"metric\":\"sum__revenue\",\"row_limit\":10000,\"color_by\":\"metric\",\"linear_color_scheme\":\"blue_white_yellow\",\"y_axis_format\":\"$,.2f\"}"
}
```

### World Map with Bubbles and Multiple Metrics

```json
{
  "slice_name": "Customer Distribution and Revenue",
  "description": "Shows customer count by country with revenue as bubble size",
  "viz_type": "world_map",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"entity\":\"country_iso\",\"country_fieldtype\":\"cca3\",\"metric\":{\"expressionType\":\"SIMPLE\",\"aggregate\":\"COUNT_DISTINCT\",\"column\":{\"column_name\":\"customer_id\"},\"label\":\"Customer Count\"},\"secondary_metric\":{\"expressionType\":\"SIMPLE\",\"aggregate\":\"SUM\",\"column\":{\"column_name\":\"revenue\"},\"label\":\"Total Revenue\"},\"show_bubbles\":true,\"max_bubble_size\":\"50\",\"color_picker\":{\"r\":0,\"g\":122,\"b\":135,\"a\":1},\"color_by\":\"metric\",\"linear_color_scheme\":\"blue_white_yellow\",\"row_limit\":10000,\"y_axis_format\":\",.0f\"}",
  "dashboards": [5, 12]
}
```

### World Map with Filters and Custom SQL Metric

```json
{
  "slice_name": "Active Users by Country (2024)",
  "description": "Displays active user count per country for the year 2024",
  "viz_type": "world_map",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"entity\":\"country_name\",\"country_fieldtype\":\"name\",\"metric\":{\"expressionType\":\"SQL\",\"sqlExpression\":\"COUNT(DISTINCT CASE WHEN last_login > NOW() - INTERVAL '30 days' THEN user_id END)\",\"label\":\"Active Users (30d)\",\"hasCustomLabel\":true},\"adhoc_filters\":[{\"col\":\"signup_date\",\"op\":\">=\",\"val\":\"2024-01-01\"},{\"col\":\"status\",\"op\":\"IN\",\"val\":[\"active\",\"premium\"]}],\"row_limit\":10000,\"sort_by_metric\":true,\"color_by\":\"metric\",\"linear_color_scheme\":\"purple_white_green\",\"y_axis_format\":\",.0f\"}",
  "cache_timeout": 3600,
  "owners": [1, 5]
}
```

### World Map with Categorical Country Colors

```json
{
  "slice_name": "Regional Distribution",
  "viz_type": "world_map",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"entity\":\"country_code\",\"country_fieldtype\":\"cca2\",\"metric\":\"count\",\"color_by\":\"country\",\"color_scheme\":\"supersetColors\",\"show_bubbles\":false,\"row_limit\":10000,\"y_axis_format\":\"SMART_NUMBER\"}",
  "dashboards": [3]
}
```

## Notes

- **Legacy Plugin**: This chart type uses the legacy API (`useLegacyApi: true`) and may have different query patterns than newer chart types
- **Country Code Formats**: Ensure your data uses consistent country codes matching the selected `country_fieldtype`. The default `cca2` expects 2-letter ISO codes like `"US"`, `"GB"`, `"FR"`
- **Bubble Display**: Bubbles only appear when `show_bubbles` is `true` and a `secondary_metric` is defined
- **Color Schemes**:
  - Use `linear_color_scheme` with sequential palettes when `color_by` is `"metric"` (represents intensity)
  - Use `color_scheme` with categorical palettes when `color_by` is `"country"` (represents categories)
- **Interactive Features**: The World Map supports interactive chart behaviors including drill-to-detail and drill-by operations
- **Performance**: For better performance with large datasets, use appropriate `row_limit` values and consider caching with `cache_timeout`
