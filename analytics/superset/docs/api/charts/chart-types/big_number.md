# Big Number (`big_number`)

## Description
The Big Number with Trendline chart showcases a single prominent metric value accompanied by a simple line chart. This visualization is designed to call attention to an important KPI (Key Performance Indicator) along with its change over time or other dimensions. The large number display makes the current metric value immediately visible, while the trendline provides visual context about the metric's historical behavior.

## When to Use
Use this chart when you need to highlight a critical metric that stakeholders need to monitor at a glance. It's particularly effective in dashboards and executive reports where you want to combine the impact of a single numeric value with the context of its trend over time. This visualization works best when the metric's historical pattern is as important as its current value.

## Example Use Cases
- Displaying monthly recurring revenue (MRR) with a trendline showing growth over the past 12 months
- Tracking daily active users (DAU) with a weekly trend comparison
- Monitoring server response time with performance trends to identify degradation
- Showing total sales for the current quarter alongside historical sales patterns
- Displaying current inventory levels with a trendline to predict stockouts

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `big_number` |
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
| x_axis | string | Yes | - | Temporal X-Axis column for the trendline |
| time_grain_sqla | string | No | 'P1D' | Time granularity for the visualization (e.g., 'P1D' for 1 day, 'P1W' for 1 week) |
| aggregation | string | No | - | Aggregation method to apply to the metric (e.g., 'sum', 'mean', 'LAST_VALUE', 'raw') |
| metric | string/object | Yes | - | Metric to display as the big number |
| adhoc_filters | array | No | [] | Filters to apply to the data |
| compare_lag | string | No | - | Based on granularity, number of time periods to compare against |
| compare_suffix | string | No | - | Suffix to apply after the percentage display |
| show_timestamp | boolean | No | false | Whether to display the timestamp |
| show_trend_line | boolean | No | true | Whether to display the trend line |
| start_y_axis_at_zero | boolean | No | true | Start y-axis at zero. When false, starts y-axis at minimum value in the data |
| time_range_fixed | boolean | No | - | Fix the trend line to the full time range specified in case filtered results do not include the start or end dates |
| color_picker | object | No | {"r": 0, "g": 122, "b": 135, "a": 1} | Fixed color for the chart elements |
| header_font_size | number | No | 0.4 | Big Number font size (0.2=Tiny, 0.3=Small, 0.4=Normal, 0.5=Large, 0.6=Huge) |
| subheader_font_size | number | No | 0.15 | Subheader font size (0.125=Tiny, 0.15=Small, 0.2=Normal, 0.3=Large, 0.4=Huge) |
| subtitle | string | No | - | Description text that shows up below your Big Number |
| subtitle_font_size | number | No | 0.15 | Subtitle font size (0.125=Tiny, 0.15=Small, 0.2=Normal, 0.3=Large, 0.4=Huge) |
| show_metric_name | boolean | No | false | Whether to display the metric name |
| metric_name_font_size | number | No | 0.15 | Metric name font size (0.125=Tiny, 0.15=Small, 0.2=Normal, 0.3=Large, 0.4=Huge) |
| show_x_axis | boolean | No | false | Whether to display the X Axis |
| show_x_axis_min_max_labels | boolean | No | false | When enabled, the axis will display labels for the minimum and maximum values of your data (only visible when show_x_axis is true) |
| show_y_axis | boolean | No | false | Whether to display the Y Axis |
| show_y_axis_min_max_labels | boolean | No | false | When enabled, the axis will display labels for the minimum and maximum values of your data (only visible when show_y_axis is true) |
| y_axis_format | string | No | 'SMART_NUMBER' | Number format for the metric value (e.g., '.2f', '.3s', ',d') |
| currency_format | object | No | - | Currency format configuration with symbol and placement |
| time_format | string | No | 'smart_date' | Date format for timestamps (e.g., '%Y-%m-%d', '%B %d, %Y') |
| force_timestamp_formatting | boolean | No | false | Use date formatting even when metric value is not a timestamp |
| rolling_type | string | No | 'None' | Rolling window function to apply ('None', 'mean', 'sum', 'std', 'cumsum') |
| rolling_periods | string | No | - | Size of the rolling window function, relative to the time granularity selected (integer) |
| min_periods | string | No | - | Minimum number of rolling periods required to show a value (integer) |
| resample_rule | string | No | null | Pandas resample rule (e.g., '1T', '1H', '1D', '7D', '1MS', '1M', '1AS', '1A') |
| resample_method | string | No | null | Pandas resample fill method ('asfreq', 'zerofill', 'linear', 'ffill', 'bfill', 'median', 'mean', 'sum') |

### Example Request
```json
{
  "slice_name": "Monthly Active Users Trend",
  "viz_type": "big_number",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"x_axis\": \"date_column\", \"time_grain_sqla\": \"P1M\", \"metric\": \"count\", \"aggregation\": \"sum\", \"show_trend_line\": true, \"start_y_axis_at_zero\": true, \"header_font_size\": 0.5, \"subheader_font_size\": 0.15, \"subtitle\": \"Total active users this month\", \"y_axis_format\": \",d\", \"color_picker\": {\"r\": 0, \"g\": 122, \"b\": 135, \"a\": 1}, \"compare_lag\": \"1\", \"compare_suffix\": \"vs last month\", \"show_timestamp\": true, \"rolling_type\": \"None\"}",
  "description": "Displays the total number of monthly active users with a trendline showing growth patterns",
  "owners": [1],
  "dashboards": [5]
}
```

## Parameter Details

### Time Granularity Options
The `time_grain_sqla` field accepts the following values:
- `PT5S` - 5 seconds
- `PT30S` - 30 seconds
- `PT1M` - 1 minute
- `PT5M` - 5 minutes
- `PT30M` - 30 minutes
- `PT1H` - 1 hour
- `PT6H` - 6 hours
- `P1D` - 1 day (default)
- `P7D` - 7 days
- `P1W` - week
- `P1M` - month
- `P3M` - quarter
- `P1Y` - year

### Aggregation Methods
The `aggregation` field supports:
- `raw` - No aggregation, use raw metric values
- `sum` - Sum values (can be computed client-side)
- `mean` - Average values (can be computed client-side)
- `LAST_VALUE` - Use the last value in the time range
- Other aggregation methods may be available depending on your data source

### Font Size Values
Font size fields use relative sizing:
- Small fonts (subheader, subtitle, metric name): 0.125 (Tiny), 0.15 (Small), 0.2 (Normal), 0.3 (Large), 0.4 (Huge)
- Large fonts (header): 0.2 (Tiny), 0.3 (Small), 0.4 (Normal), 0.5 (Large), 0.6 (Huge)

### Number Format Patterns
The `y_axis_format` field accepts D3 format strings:
- `,d` - Comma-separated integers (e.g., 1,234)
- `.2f` - Fixed decimal with 2 places (e.g., 123.45)
- `.3s` - SI-prefix with 3 significant digits (e.g., 1.23k)
- `.2%` - Percentage with 2 decimal places (e.g., 12.34%)
- `$,.2f` - Currency format (e.g., $1,234.56)

### Rolling Window Functions
When using advanced analytics with rolling windows:
- `rolling_type`: Choose aggregation function (mean, sum, std, cumsum)
- `rolling_periods`: Number of periods to include in the window
- `min_periods`: Minimum periods required before showing values (helps hide "ramp up" data)

### Resampling
For time series data manipulation:
- `resample_rule`: Time frequency to resample to (e.g., '1D' for daily, '1H' for hourly)
- `resample_method`: How to fill missing values after resampling (forward fill, backward fill, linear interpolation, etc.)
