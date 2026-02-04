# Gauge Chart (`gauge_chart`)

## Description
The Gauge Chart uses a circular gauge visualization to showcase the progress of a metric towards a target value. The position of the dial or progress bar represents the current value, while the gauge axis displays the range from minimum to maximum values. This chart type is built using Apache ECharts and supports customization of angles, intervals, colors, and display options.

## When to Use
Use a Gauge Chart when you need to display a single metric's progress towards a goal or within a defined range. This chart is particularly effective for KPIs, performance metrics, or any measurement where understanding the current value in relation to minimum and maximum thresholds is important. It works best for displaying 1-10 data points simultaneously.

## Example Use Cases
- Displaying sales performance against quarterly targets
- Monitoring server CPU usage within safe operating ranges
- Tracking project completion percentage
- Showing customer satisfaction scores on a scale
- Visualizing equipment temperature or pressure readings with safety thresholds

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `gauge_chart` |
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

The `params` field must be a JSON string containing an object with the following properties:

#### Query Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| groupby | array | No | [] | Columns to group by. Array of column names for categorizing data. |
| metric | string/object | Yes | - | Metric to display. Can be a column name or an adhoc metric object with aggregation function. |
| adhoc_filters | array | No | [] | Custom filters to apply to the query. Array of filter objects. |
| row_limit | integer | No | 10 | Maximum number of rows to return. Limited to 1-10 for gauge charts. |
| sort_by_metric | boolean | No | false | Whether to sort results by the selected metric in descending order. |

#### General Chart Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| min_val | integer/null | No | null | Minimum value on the gauge axis. If null, automatically determined from data. |
| max_val | integer/null | No | null | Maximum value on the gauge axis. If null, automatically determined from data. |
| start_angle | integer | No | 225 | Angle at which to start the progress axis (in degrees). Default creates a 3/4 circle gauge starting from bottom-left. |
| end_angle | integer | No | -45 | Angle at which to end the progress axis (in degrees). Default completes the 3/4 circle at bottom-right. |
| color_scheme | string | No | - | Color scheme to use for the gauge. Must be a valid color scheme name from the registry. |
| font_size | integer | No | 15 | Font size for axis labels, detail value, and other text elements. Range: 10-20. |
| number_format | string | No | "SMART_NUMBER" | D3 format string for number formatting (see https://github.com/d3/d3-format). |
| currency_format | object | No | - | Currency formatting configuration with symbol and code properties. |
| value_formatter | string | No | "{value}" | Additional text to add before or after the value (e.g., unit labels like "mph" or "$"). Use {value} as placeholder. |
| show_pointer | boolean | No | true | Whether to show the pointer/needle on the gauge. |
| animation | boolean | No | true | Whether to animate the progress and value or display them immediately. |

#### Axis Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| show_axis_tick | boolean | No | false | Whether to show minor tick marks on the axis. |
| show_split_line | boolean | No | false | Whether to show split lines on the axis. |
| split_number | integer | No | 10 | Number of split segments on the axis. Range: 3-30. |

#### Progress Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| show_progress | boolean | No | true | Whether to show the progress bar on the gauge. |
| overlap | boolean | No | true | Whether progress bars overlap when there are multiple groups of data. |
| round_cap | boolean | No | false | Style the ends of the progress bar with a round cap instead of flat edges. |

#### Interval Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| intervals | string | No | "" | Comma-separated interval bounds (e.g., "2,4,5" for intervals 0-2, 2-4, and 4-5). Last number should match max_val. |
| interval_color_indices | string | No | "" | Comma-separated color picks for intervals (e.g., "1,2,4"). Integers denote colors from the chosen color scheme and are 1-indexed. Length must match the number of intervals. |

### Example Request

```json
{
  "slice_name": "Sales Performance Q1 2024",
  "description": "Quarterly sales performance against target",
  "viz_type": "gauge_chart",
  "datasource_id": 123,
  "datasource_type": "table",
  "params": "{\"groupby\":[\"region\"],\"metric\":{\"expressionType\":\"SIMPLE\",\"column\":{\"column_name\":\"sales_amount\",\"type\":\"DOUBLE\"},\"aggregate\":\"SUM\",\"label\":\"Total Sales\"},\"adhoc_filters\":[{\"clause\":\"WHERE\",\"expressionType\":\"SIMPLE\",\"subject\":\"quarter\",\"operator\":\"==\",\"comparator\":\"Q1\"}],\"row_limit\":5,\"sort_by_metric\":true,\"min_val\":0,\"max_val\":1000000,\"start_angle\":225,\"end_angle\":-45,\"color_scheme\":\"supersetColors\",\"font_size\":15,\"number_format\":\"$,.0f\",\"value_formatter\":\"{value}\",\"show_pointer\":true,\"animation\":true,\"show_axis_tick\":true,\"show_split_line\":true,\"split_number\":10,\"show_progress\":true,\"overlap\":true,\"round_cap\":true,\"intervals\":\"300000,600000,1000000\",\"interval_color_indices\":\"1,2,3\"}",
  "cache_timeout": 3600,
  "owners": [1],
  "dashboards": [45],
  "certified_by": "Analytics Team",
  "certification_details": "Verified against Q1 2024 sales data"
}
```

### Example with Simple Metric

```json
{
  "slice_name": "Server CPU Usage",
  "viz_type": "gauge_chart",
  "datasource_id": 456,
  "datasource_type": "table",
  "params": "{\"metric\":\"avg_cpu_usage\",\"row_limit\":1,\"min_val\":0,\"max_val\":100,\"number_format\":\".1f\",\"value_formatter\":\"{value}%\",\"show_progress\":true,\"show_pointer\":true,\"animation\":true,\"intervals\":\"60,80,100\",\"interval_color_indices\":\"2,3,1\",\"color_scheme\":\"bnbColors\"}",
  "cache_timeout": 60
}
```

## Notes

- The gauge chart supports interactive behaviors including drill-to-detail and drill-by operations
- When using multiple groups (via `groupby`), each group will display as a separate gauge up to the `row_limit`
- Interval colors are 1-indexed, meaning "1" refers to the first color in the selected color scheme
- The `start_angle` and `end_angle` work together to define the gauge's arc. A full circle would use 0 and 360
- If `min_val` or `max_val` are not specified, they will be automatically calculated from the data
- The `value_formatter` field supports the `{value}` placeholder which will be replaced with the formatted metric value
- When `animation` is disabled, the gauge displays its final state immediately without transition effects
