# Calendar Heatmap (`cal_heatmap`)

## Description

The Calendar Heatmap visualizes how a metric has changed over time using a color scale and a calendar view. It displays data in a grid format where each cell represents a time period (such as a day, hour, or week), and the cell's color intensity indicates the magnitude of the metric value for that period. Gray values indicate missing data, and a linear color scheme encodes the magnitude of each period's value.

## When to Use

Use a Calendar Heatmap when you need to identify patterns, trends, or anomalies in time-series data over extended periods. This visualization is particularly effective for showing temporal patterns like seasonality, weekly cycles, or recurring events. It works best with single-metric data aggregated over regular time intervals where you want to compare intensity across days, weeks, months, or years at a glance.

## Example Use Cases

- **Website Traffic Analysis**: Visualize daily page views or user sessions to identify peak traffic days and seasonal patterns
- **Sales Performance Tracking**: Display daily or weekly sales revenue to spot trends, identify slow periods, and plan inventory
- **System Health Monitoring**: Track daily error rates, server uptime percentages, or API response times to detect anomalies
- **Employee Productivity**: Monitor task completion rates, support ticket resolutions, or time logged per day across teams
- **Social Media Engagement**: Analyze daily post engagement metrics like likes, shares, or comments to optimize posting schedules

## Request Format

### Common Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `cal_heatmap` |
| datasource_id | integer | Yes | ID of the datasource |
| datasource_type | string | Yes | Type of datasource (e.g., `table`, `query`) |
| params | string | Yes | JSON string containing chart-specific parameters (see below) |
| description | string | No | Chart description |
| owners | array[integer] | No | List of owner user IDs |
| cache_timeout | integer | No | Cache timeout in seconds (overrides datasource default) |
| dashboards | array[integer] | No | List of dashboard IDs to add chart to |
| certified_by | string | No | Name of certifier |
| certification_details | string | No | Certification details |

### params Object

The `params` field must be a JSON string containing an object with the following properties:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| domain_granularity | string | No | `month` | The time unit used for grouping of blocks. Options: `hour`, `day`, `week`, `month`, `year` |
| subdomain_granularity | string | No | `day` | The time unit for each block/cell. Should be smaller than domain_granularity and larger or equal to the time grain. Options: `min`, `hour`, `day`, `week`, `month` |
| granularity_sqla | string | Yes | - | Name of the temporal column used for time filtering from the datasource |
| time_range | string | No | `No filter` | Time range filter (e.g., `Last week`, `Last 30 days`, or ISO 8601 format like `2024-01-01 : 2024-12-31`) |
| time_grain_sqla | string | No | `P1D` | Time grain for aggregation. Supports ISO 8601 durations (e.g., `P1D` for 1 day, `PT1H` for 1 hour) |
| metrics | array | Yes | - | List of metrics to aggregate. Can be metric names (strings) or adhoc metric objects |
| adhoc_filters | array | No | `[]` | List of adhoc filter objects to apply to the query |
| linear_color_scheme | string | No | (default scheme) | Color scheme ID for the heatmap gradient (e.g., `blue_white_yellow`, `schemeYlOrRd`) |
| cell_size | integer | No | `10` | The size of each square cell in pixels |
| cell_padding | integer | No | `2` | The distance between cells in pixels |
| cell_radius | integer | No | `0` | The pixel radius for rounded cell corners (0 = square) |
| steps | integer | No | `10` | The number of color steps/gradations in the color scale |
| y_axis_format | string | No | `SMART_NUMBER` | D3 format string for metric values (e.g., `.2f`, `.3s`, `,.0f`). See [D3 format docs](https://github.com/d3/d3-format) |
| x_axis_time_format | string | No | `smart_date` | D3 time format string for date labels (e.g., `%Y-%m-%d`, `%B %d`). See [D3 time format docs](https://github.com/d3/d3-time-format) |
| show_legend | boolean | No | `true` | Whether to display the color legend |
| show_values | boolean | No | `false` | Whether to display numerical values within the cells |
| show_metric_name | boolean | No | `true` | Whether to display the metric name as a title |

#### Adhoc Metric Object Structure

When defining custom metrics inline, use this structure:

```json
{
  "expressionType": "SIMPLE",
  "column": {
    "column_name": "column_name",
    "type": "BIGINT"
  },
  "aggregate": "SUM",
  "label": "My Custom Metric",
  "hasCustomLabel": true,
  "optionName": "metric_abc123"
}
```

For SQL-based metrics:

```json
{
  "expressionType": "SQL",
  "sqlExpression": "SUM(revenue) / COUNT(orders)",
  "label": "Average Order Value",
  "hasCustomLabel": true
}
```

#### Adhoc Filter Object Structure

```json
{
  "col": "country",
  "op": "IN",
  "val": ["USA", "Canada", "Mexico"]
}
```

Common operators: `IN`, `NOT IN`, `==`, `!=`, `>`, `<`, `>=`, `<=`, `LIKE`, `IS NULL`, `IS NOT NULL`

### Example Request

```json
{
  "slice_name": "Daily Sales Revenue Heatmap",
  "description": "Calendar view of daily sales revenue for the current year",
  "viz_type": "cal_heatmap",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"domain_granularity\":\"month\",\"subdomain_granularity\":\"day\",\"granularity_sqla\":\"order_date\",\"time_range\":\"Last year\",\"time_grain_sqla\":\"P1D\",\"metrics\":[\"sum__revenue\"],\"adhoc_filters\":[{\"col\":\"status\",\"op\":\"==\",\"val\":\"completed\"}],\"linear_color_scheme\":\"blue_white_yellow\",\"cell_size\":15,\"cell_padding\":3,\"cell_radius\":2,\"steps\":10,\"y_axis_format\":\"$,.2f\",\"x_axis_time_format\":\"%b %d\",\"show_legend\":true,\"show_values\":false,\"show_metric_name\":true}",
  "cache_timeout": 3600,
  "owners": [123],
  "dashboards": [456],
  "certified_by": "Analytics Team",
  "certification_details": "Verified against financial system data"
}
```

### Example Request with Adhoc Metric

```json
{
  "slice_name": "Customer Activity Heatmap",
  "viz_type": "cal_heatmap",
  "datasource_id": 15,
  "datasource_type": "table",
  "params": "{\"domain_granularity\":\"week\",\"subdomain_granularity\":\"day\",\"granularity_sqla\":\"activity_timestamp\",\"time_range\":\"Last 90 days\",\"metrics\":[{\"expressionType\":\"SIMPLE\",\"column\":{\"column_name\":\"user_id\",\"type\":\"VARCHAR\"},\"aggregate\":\"COUNT_DISTINCT\",\"label\":\"Unique Users\",\"hasCustomLabel\":true}],\"adhoc_filters\":[{\"col\":\"activity_type\",\"op\":\"IN\",\"val\":[\"login\",\"purchase\",\"review\"]}],\"linear_color_scheme\":\"schemeGnBu\",\"cell_size\":12,\"cell_padding\":2,\"steps\":8,\"y_axis_format\":\".0f\",\"show_legend\":true,\"show_values\":true,\"show_metric_name\":true}"
}
```

## Response Format

The API returns a chart object with an `id` that can be used to retrieve chart data or embed the visualization. See the [Charts API documentation](/docs/api/charts) for details on the response schema.

## Notes

- The `subdomain_granularity` should always be smaller than or equal to the `domain_granularity` to ensure proper nesting
- The `time_grain_sqla` should match or be compatible with the `subdomain_granularity` for accurate aggregation
- Gray cells indicate missing or null values in the dataset for that time period
- The `steps` parameter controls how many distinct color levels appear in the gradient - higher values create smoother transitions
- Cell appearance can be customized through `cell_size`, `cell_padding`, and `cell_radius` to optimize for different display sizes
- This visualization uses the legacy API (`useLegacyApi: true`), which means it relies on the older data format

## Related Chart Types

- **Heatmap**: For non-temporal heatmaps showing relationships between two categorical dimensions
- **Time Series Line Chart**: For showing precise metric values over time with continuous lines
- **Time Series Bar Chart**: For comparing discrete time periods with bar heights
