# Big Number Period Over Period (`pop_kpi`)

## Description
The Big Number with Time Period Comparison chart displays a single metric value prominently along with comparison statistics from a previous time period. It shows the current value, the previous period's value, the absolute change (delta), and the percentage change between periods, making it ideal for tracking KPI performance over time.

## When to Use
Use this chart type when you need to monitor a single key performance indicator and understand how it has changed compared to a previous time period. It is particularly effective for executive dashboards, business reports, and real-time monitoring displays where quick visual assessment of metric trends is essential.

## Example Use Cases
- Monthly revenue tracking with comparison to the previous month
- Daily active users compared to the same day last week or last year
- Sales conversion rates with week-over-week change tracking
- Website traffic metrics compared to the previous time period
- Customer satisfaction scores with period-over-period trend analysis
- Inventory levels with comparison to last quarter
- Operating expenses tracking with year-over-year comparison

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `pop_kpi` |
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
The `params` field must contain a JSON string with the following parameters:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| metric | object/string | Yes | - | The metric to display. Can be a saved metric name or an adhoc metric object with aggregation function and column |
| adhoc_filters | array | No | [] | List of adhoc filter objects to filter the data |
| row_limit | integer | No | 10000 | Limits the number of rows computed in the source query (max depends on SQL_MAX_ROW configuration) |
| y_axis_format | string | No | SMART_NUMBER | Number format for the main metric value using D3 format strings (e.g., '.2f', '.3s', ',.2%') |
| percentDifferenceFormat | string | No | SMART_NUMBER | Number format for the percent difference value using D3 format strings |
| currency_format | object | No | - | Currency formatting configuration with symbol and position settings |
| header_font_size | number | No | 0.2 | Font size for the big number value (0.2=Normal, 0.3=Large, 0.4=Huge) |
| subtitle | string | No | - | Custom subtitle text that appears below the big number |
| subtitle_font_size | number | No | 0.15 | Font size for the subtitle (0.125=Tiny, 0.15=Small, 0.2=Normal, 0.3=Large, 0.4=Huge) |
| show_metric_name | boolean | No | false | Whether to display the metric name in the visualization |
| metric_name_font_size | number | No | 0.15 | Font size for the metric name when displayed (0.125=Tiny, 0.15=Small, 0.2=Normal, 0.3=Large, 0.4=Huge) |
| subheader_font_size | number | No | 0.125 | Font size for the comparison value display (0.125=Tiny, 0.15=Small, 0.2=Normal, 0.3=Large, 0.4=Huge) |
| comparison_color_enabled | boolean | No | false | Whether to add color coding for positive/negative changes |
| comparison_color_scheme | string | No | "Green" | Color scheme for comparison: "Green" (green for increase, red for decrease) or "Red" (red for increase, green for decrease) |
| column_config | object | No | - | Configuration for customizing the display of comparison columns (Previous value, Delta, Percent change) including custom names, visibility, and display type icons |
| time_compare | string/array | No | - | Time shift for comparison (e.g., "1 day ago", "1 week ago", "1 month ago", "1 year ago", "custom", "inherit"). For pop_kpi, use single value (not array) |
| start_date_offset | string | No | - | Custom start date offset when time_compare is set to "custom". Required when using custom time comparison |
| comparison_type | string | No | "values" | How to display time shifts (hidden for this chart, but available): "values", "difference", "percentage", "ratio" |

### Example Request
```json
{
  "slice_name": "Monthly Revenue Performance",
  "viz_type": "pop_kpi",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"metric\":{\"expressionType\":\"SIMPLE\",\"column\":{\"column_name\":\"revenue\",\"type\":\"DOUBLE\"},\"aggregate\":\"SUM\",\"label\":\"Total Revenue\"},\"adhoc_filters\":[],\"row_limit\":10000,\"y_axis_format\":\"$,.2f\",\"percentDifferenceFormat\":\".1%\",\"header_font_size\":0.4,\"subtitle\":\"Total monthly revenue with MoM comparison\",\"subtitle_font_size\":0.15,\"show_metric_name\":true,\"metric_name_font_size\":0.15,\"subheader_font_size\":0.125,\"comparison_color_enabled\":true,\"comparison_color_scheme\":\"Green\",\"time_compare\":\"1 month ago\",\"column_config\":{\"Previous value\":{\"visible\":true},\"Delta\":{\"visible\":true},\"Percent change\":{\"visible\":true}}}",
  "description": "Monthly revenue with month-over-month comparison",
  "owners": [1],
  "dashboards": [5],
  "cache_timeout": 3600
}
```

## Notes

### Time Comparison Configuration
The `time_compare` parameter accepts several predefined options:
- `"1 day ago"` - Compare with the previous day
- `"1 week ago"` - Compare with the same day last week
- `"28 days ago"` - Compare with 28 days prior
- `"30 days ago"` - Compare with 30 days prior
- `"1 month ago"` - Compare with the previous month
- `"52 weeks ago"` - Compare with the same week last year
- `"1 year ago"` - Compare with the same date last year
- `"104 weeks ago"` - Compare with 2 years ago
- `"2 years ago"` - Compare with 2 years prior
- `"156 weeks ago"` - Compare with 3 years ago
- `"3 years ago"` - Compare with 3 years prior
- `"custom"` - Use a custom date offset (requires `start_date_offset` parameter)
- `"inherit"` - Inherit range from time filter

### Number Format Options
Both `y_axis_format` and `percentDifferenceFormat` accept D3 format strings:
- `"SMART_NUMBER"` - Automatic intelligent formatting
- `".2f"` - Fixed decimal with 2 places (e.g., 12.34)
- `",.0f"` - Thousands separator, no decimals (e.g., 1,234)
- `".3s"` - SI prefix with 3 significant digits (e.g., 1.23k)
- `".1%"` - Percentage with 1 decimal place (e.g., 12.3%)
- `"$,.2f"` - Currency format with 2 decimals (e.g., $1,234.56)

### Metric Configuration
The `metric` parameter can be either:
- A string referencing a saved metric name from the datasource
- An adhoc metric object with the following structure:
```json
{
  "expressionType": "SIMPLE",
  "column": {
    "column_name": "column_name",
    "type": "BIGINT"
  },
  "aggregate": "SUM",
  "label": "Metric Label"
}
```

### Column Configuration
The `column_config` parameter allows customization of the three comparison columns:
- **Previous value**: The metric value from the comparison time period
- **Delta**: The absolute change between current and previous values
- **Percent change**: The percentage change between current and previous values

Each column can be configured with:
- `customColumnName`: Custom display name for the column
- `displayTypeIcon`: Whether to show a type indicator icon
- `visible`: Whether to display the column in the visualization
