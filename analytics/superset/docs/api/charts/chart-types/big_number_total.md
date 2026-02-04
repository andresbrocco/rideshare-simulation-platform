# Big Number Total (`big_number_total`)

## Description
The Big Number Total chart showcases a single metric in a large, prominent display format. It's designed to call immediate attention to a key performance indicator (KPI) or critical metric, displaying the value front-and-center with optional subtitle text below for additional context.

## When to Use
Use Big Number Total when you want to focus your audience's attention on one specific metric or KPI. This chart type is ideal for executive dashboards, status displays, or any scenario where a single number tells the most important part of the story.

## Example Use Cases
- Display total revenue for the current quarter on an executive dashboard
- Show the current number of active users or customers
- Monitor real-time inventory levels or stock counts
- Track total sales, orders, or conversions for a given time period
- Display key operational metrics like uptime percentage or error counts

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `big_number_total` |
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
The `params` field must be a JSON-encoded string containing an object with the following fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| metric | object or string | Yes | null | The metric to display. Can be a metric name (string) or an adhoc metric object with aggregation function and column |
| adhoc_filters | array | No | [] | List of adhoc filter objects to filter the data |
| header_font_size | number | No | 0.4 | Font size for the big number display as a fraction of chart height. Options: 0.2 (Tiny), 0.3 (Small), 0.4 (Normal), 0.5 (Large), 0.6 (Huge) |
| subtitle | string | No | "" | Description text that shows up below your Big Number |
| subtitle_font_size | number | No | 0.15 | Font size for the subtitle as a fraction of chart height. Options: 0.125 (Tiny), 0.15 (Small), 0.2 (Normal), 0.3 (Large), 0.4 (Huge) |
| show_metric_name | boolean | No | false | Whether to display the metric name below the big number |
| metric_name_font_size | number | No | 0.15 | Font size for the metric name as a fraction of chart height. Only applies when show_metric_name is true. Options: 0.125 (Tiny), 0.15 (Small), 0.2 (Normal), 0.3 (Large), 0.4 (Huge) |
| y_axis_format | string | No | "SMART_NUMBER" | Number format string using D3 format syntax (e.g., ".2f", ".3s", ",.0f") |
| currency_format | object | No | null | Currency formatting configuration with symbol and position |
| time_format | string | No | "smart_date" | Date format string for timestamp values using D3 time format syntax |
| force_timestamp_formatting | boolean | No | false | Use date formatting even when metric value is not a timestamp |
| conditional_formatting | array | No | [] | Array of conditional formatting rules to apply color formatting based on metric value |

### Metric Object Format
When specifying an adhoc metric (instead of a saved metric name), use this structure:

```json
{
  "expressionType": "SIMPLE",
  "column": {
    "column_name": "column_name",
    "type": "BIGINT"
  },
  "aggregate": "SUM",
  "label": "My Metric"
}
```

Or for SQL expression metrics:

```json
{
  "expressionType": "SQL",
  "sqlExpression": "COUNT(DISTINCT user_id)",
  "label": "Unique Users"
}
```

### Adhoc Filter Object Format
```json
{
  "clause": "WHERE",
  "expressionType": "SIMPLE",
  "comparator": "value",
  "operator": "==",
  "subject": "column_name"
}
```

Or for SQL expression filters:

```json
{
  "clause": "WHERE",
  "expressionType": "SQL",
  "sqlExpression": "column_name > 100"
}
```

### Conditional Formatting Object Format
```json
{
  "column": "metric_column",
  "operator": ">",
  "targetValue": 1000,
  "colorScheme": "#FF0000"
}
```

### Example Request
```json
{
  "slice_name": "Total Revenue Q4 2024",
  "viz_type": "big_number_total",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"metric\":{\"expressionType\":\"SIMPLE\",\"column\":{\"column_name\":\"revenue\",\"type\":\"DOUBLE\"},\"aggregate\":\"SUM\",\"label\":\"Total Revenue\"},\"adhoc_filters\":[{\"clause\":\"WHERE\",\"expressionType\":\"SIMPLE\",\"comparator\":\"2024-Q4\",\"operator\":\"TEMPORAL_RANGE\",\"subject\":\"date_column\"}],\"header_font_size\":0.5,\"subtitle\":\"Year-over-year growth: +15%\",\"subtitle_font_size\":0.15,\"show_metric_name\":true,\"metric_name_font_size\":0.15,\"y_axis_format\":\"$,.2f\",\"time_format\":\"smart_date\",\"force_timestamp_formatting\":false,\"conditional_formatting\":[{\"column\":\"revenue\",\"operator\":\">\",\"targetValue\":1000000,\"colorScheme\":\"#00FF00\"}]}",
  "description": "Displays total revenue for Q4 2024 with conditional green formatting for values over $1M",
  "owners": [1],
  "dashboards": [5]
}
```

### Simplified Example with Saved Metric
```json
{
  "slice_name": "Active Users",
  "viz_type": "big_number_total",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"metric\":\"count_distinct_users\",\"subtitle\":\"Last 30 days\",\"y_axis_format\":\",.0f\",\"header_font_size\":0.4}",
  "description": "Total active users in the last 30 days"
}
```

## Notes
- The Big Number Total chart requires exactly one metric to display
- Font sizes are specified as fractions of the chart height (0.0 to 1.0), allowing the visualization to scale proportionally
- The `y_axis_format` field uses D3 format syntax for number formatting. Common patterns include:
  - `,.0f` - Comma-separated integer (1,234)
  - `.2f` - Two decimal places (12.34)
  - `.3s` - SI prefix with 3 significant digits (1.23k)
  - `$,.2f` - Currency format ($1,234.56)
  - `.1%` - Percentage with one decimal (12.3%)
- Conditional formatting allows dynamic color changes based on the metric value, useful for visual status indicators
- When `force_timestamp_formatting` is enabled, numeric values will be treated as Unix timestamps and formatted according to the `time_format` setting
