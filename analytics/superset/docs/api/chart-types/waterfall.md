# Waterfall Chart (`waterfall`)

## Description
The Waterfall Chart is a form of data visualization that helps in understanding the cumulative effect of sequentially introduced positive or negative values. These intermediate values can either be time-based or category-based, displaying how an initial value is affected by a series of positive and negative changes. This chart is powered by Apache ECharts and is particularly effective for visualizing financial data, inventory changes, or any metric that shows incremental changes over time or across categories.

## When to Use
Use a Waterfall Chart when you need to visualize how an initial value is incrementally affected by a series of positive and negative contributions, ultimately reaching a final cumulative total. This chart type excels at showing the sequential impact of increases and decreases, making it easy to identify which factors drive overall change.

## Example Use Cases
- Financial profit and loss analysis showing revenue, expenses, and net profit
- Inventory management tracking stock levels with additions and depletions
- Budget variance analysis comparing planned versus actual spending
- Cash flow statement visualization showing sources and uses of cash
- Project resource allocation showing cumulative time or cost changes across phases

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `waterfall` |
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

The `params` field must be a JSON-encoded string containing the following parameters:

#### Query Parameters
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis | string or object | Yes | - | Column to use for the X-axis categories or time dimension |
| time_grain_sqla | string | No | - | Time granularity for temporal X-axis (e.g., 'P1D' for daily, 'P1W' for weekly) |
| groupby | array | No | `[]` | Single column for breaking down the series by category. Shows how each category affects the overall value (max 1 item) |
| metric | string or object | Yes | - | Metric to display (aggregation function or custom SQL expression) |
| adhoc_filters | array | No | `[]` | Array of ad-hoc filter objects for filtering data |
| row_limit | integer | No | `10000` | Maximum number of rows to retrieve from the datasource |

#### Chart Options
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| show_value | boolean | No | `false` | Whether to display values directly on the chart bars |
| show_legend | boolean | No | `false` | Whether to display a legend for the chart |

#### Series Settings
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| increase_color | object | No | `{"r":90,"g":193,"b":137,"a":1}` | RGBA color object for bars representing increases (default: green) |
| increase_label | string | No | - | Custom label for increasing values in tooltips and legend |
| decrease_color | object | No | `{"r":224,"g":67,"b":85,"a":1}` | RGBA color object for bars representing decreases (default: red) |
| decrease_label | string | No | - | Custom label for decreasing values in tooltips and legend |
| show_total | boolean | No | `true` | Whether to display the cumulative total bar at the end of the chart |
| total_color | object | No | `{"r":102,"g":102,"b":102,"a":1}` | RGBA color object for the total bar (default: gray) |
| total_label | string | No | - | Custom label for the total value in tooltips, legend, and chart axis |

#### X Axis Settings
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis_label | string | No | `''` | Label text to display for the X-axis |
| x_axis_time_format | string | No | `'smart_date'` | D3 time format string for temporal X-axis labels (e.g., '%Y-%m-%d', '%b %Y'). See [D3 time format documentation](https://github.com/d3/d3-time-format) |
| x_ticks_layout | string | No | `'auto'` | Layout orientation for X-axis tick labels. Options: `'auto'`, `'flat'`, `'45°'`, `'90°'`, `'staggered'` |

#### Y Axis Settings
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| y_axis_label | string | No | `''` | Label text to display for the Y-axis |
| y_axis_format | string | No | `'SMART_NUMBER'` | D3 number format string for Y-axis values (e.g., `',.0f'`, `'.2f'`, `'.2%'`) |
| currency_format | object | No | - | Currency formatting configuration with symbol and position properties |

### Example Request

```json
{
  "slice_name": "Monthly Revenue Waterfall",
  "description": "Shows monthly revenue changes from Q1 starting point to Q1 ending balance",
  "viz_type": "waterfall",
  "datasource_id": 123,
  "datasource_type": "table",
  "params": "{\"x_axis\":\"month\",\"metric\":{\"expressionType\":\"SIMPLE\",\"column\":{\"column_name\":\"revenue_change\",\"type\":\"DECIMAL\"},\"aggregate\":\"SUM\",\"label\":\"Revenue Change\"},\"adhoc_filters\":[{\"expressionType\":\"SIMPLE\",\"subject\":\"fiscal_quarter\",\"operator\":\"==\",\"comparator\":\"Q1\",\"clause\":\"WHERE\"}],\"row_limit\":10000,\"show_value\":true,\"show_legend\":true,\"increase_color\":{\"r\":90,\"g\":193,\"b\":137,\"a\":1},\"increase_label\":\"Revenue Gain\",\"decrease_color\":{\"r\":224,\"g\":67,\"b\":85,\"a\":1},\"decrease_label\":\"Revenue Loss\",\"show_total\":true,\"total_color\":{\"r\":102,\"g\":102,\"b\":102,\"a\":1},\"total_label\":\"Q1 Total\",\"x_axis_label\":\"Month\",\"x_ticks_layout\":\"auto\",\"y_axis_label\":\"Revenue ($)\",\"y_axis_format\":\"$,.0f\"}",
  "cache_timeout": 3600,
  "owners": [1],
  "dashboards": [5]
}
```

### Example params Object (before JSON encoding)

```json
{
  "x_axis": "month",
  "metric": {
    "expressionType": "SIMPLE",
    "column": {
      "column_name": "revenue_change",
      "type": "DECIMAL"
    },
    "aggregate": "SUM",
    "label": "Revenue Change"
  },
  "adhoc_filters": [
    {
      "expressionType": "SIMPLE",
      "subject": "fiscal_quarter",
      "operator": "==",
      "comparator": "Q1",
      "clause": "WHERE"
    }
  ],
  "row_limit": 10000,
  "show_value": true,
  "show_legend": true,
  "increase_color": {
    "r": 90,
    "g": 193,
    "b": 137,
    "a": 1
  },
  "increase_label": "Revenue Gain",
  "decrease_color": {
    "r": 224,
    "g": 67,
    "b": 85,
    "a": 1
  },
  "decrease_label": "Revenue Loss",
  "show_total": true,
  "total_color": {
    "r": 102,
    "g": 102,
    "b": 102,
    "a": 1
  },
  "total_label": "Q1 Total",
  "x_axis_label": "Month",
  "x_ticks_layout": "auto",
  "y_axis_label": "Revenue ($)",
  "y_axis_format": "$,.0f"
}
```

### Example with Temporal X-Axis

```json
{
  "x_axis": {
    "expressionType": "SIMPLE",
    "column": {
      "column_name": "transaction_date",
      "type": "TIMESTAMP"
    },
    "label": "Date"
  },
  "time_grain_sqla": "P1D",
  "metric": {
    "expressionType": "SIMPLE",
    "column": {
      "column_name": "amount",
      "type": "DECIMAL"
    },
    "aggregate": "SUM",
    "label": "Daily Change"
  },
  "adhoc_filters": [
    {
      "expressionType": "SIMPLE",
      "subject": "transaction_date",
      "operator": "TEMPORAL_RANGE",
      "comparator": "Last week",
      "clause": "WHERE"
    }
  ],
  "row_limit": 10000,
  "show_value": false,
  "show_legend": true,
  "show_total": true,
  "x_axis_label": "Date",
  "x_axis_time_format": "%b %d",
  "x_ticks_layout": "45°",
  "y_axis_label": "Cash Flow",
  "y_axis_format": "SMART_NUMBER"
}
```

### Example with Breakdown by Category

```json
{
  "x_axis": "department",
  "groupby": ["expense_type"],
  "metric": {
    "expressionType": "SIMPLE",
    "column": {
      "column_name": "variance",
      "type": "DECIMAL"
    },
    "aggregate": "SUM",
    "label": "Budget Variance"
  },
  "adhoc_filters": [],
  "row_limit": 10000,
  "show_value": true,
  "show_legend": true,
  "increase_color": {
    "r": 90,
    "g": 193,
    "b": 137,
    "a": 1
  },
  "increase_label": "Over Budget",
  "decrease_color": {
    "r": 224,
    "g": 67,
    "b": 85,
    "a": 1
  },
  "decrease_label": "Under Budget",
  "show_total": true,
  "total_label": "Net Variance",
  "x_axis_label": "Department",
  "x_ticks_layout": "auto",
  "y_axis_label": "Variance ($)",
  "y_axis_format": "$,.2f"
}
```

## Response Format

A successful chart creation returns a JSON object with the chart details:

```json
{
  "id": 456,
  "slice_name": "Monthly Revenue Waterfall",
  "description": "Shows monthly revenue changes from Q1 starting point to Q1 ending balance",
  "viz_type": "waterfall",
  "datasource_id": 123,
  "datasource_type": "table",
  "cache_timeout": 3600,
  "owners": [
    {
      "id": 1,
      "username": "admin"
    }
  ],
  "params": "{...}",
  "created_on_delta_humanized": "a few seconds ago",
  "changed_on_delta_humanized": "a few seconds ago"
}
```

## Notes

### Color Configuration
Colors are specified as RGBA objects with properties:
- **r**: Red component (0-255)
- **g**: Green component (0-255)
- **b**: Blue component (0-255)
- **a**: Alpha/transparency (0-1, where 1 is fully opaque)

Default colors:
- **Increase**: Green `{"r":90,"g":193,"b":137,"a":1}` - #5AC189
- **Decrease**: Red `{"r":224,"g":67,"b":85,"a":1}` - #E04355
- **Total**: Gray `{"r":102,"g":102,"b":102,"a":1}` - #666666

### X-Axis Tick Layout Options
- **auto**: Automatically determines the best layout based on label length and chart width
- **flat**: Displays labels horizontally without rotation
- **45°**: Rotates labels 45 degrees for better readability with longer text
- **90°**: Rotates labels vertically (90 degrees)
- **staggered**: Alternates label positions vertically to prevent overlap

### Number Format
The `y_axis_format` field accepts D3 format strings. Common examples:
- `SMART_NUMBER`: Automatically formats numbers with appropriate suffixes (K, M, B)
- `,.0f`: Comma-separated integer (e.g., 1,234)
- `.2f`: Decimal with 2 places (e.g., 1234.56)
- `.2%`: Percentage with 2 decimal places (e.g., 12.34%)
- `$,.2f`: Currency format (e.g., $1,234.56)

For more format options, see [D3 format documentation](https://github.com/d3/d3-format).

### Time Format
The `x_axis_time_format` field accepts D3 time format strings. Common examples:
- `smart_date`: Automatically selects appropriate format based on time range
- `%Y-%m-%d`: ISO date format (e.g., 2024-01-15)
- `%b %d, %Y`: Month day, year (e.g., Jan 15, 2024)
- `%B %Y`: Full month and year (e.g., January 2024)
- `%m/%d/%Y`: US date format (e.g., 01/15/2024)

For more format options, see [D3 time format documentation](https://github.com/d3/d3-time-format).

### Groupby Limitations
The `groupby` parameter accepts only a single column (not multi-valued). When specified, the chart breaks down the waterfall series by the selected category, showing how each category contributes to increases or decreases in the overall cumulative value. This helps viewers understand categorical contributions to the total change.

### Data Requirements
- The metric should represent incremental changes (positive or negative values)
- Positive values will be rendered as increases (default green bars)
- Negative values will be rendered as decreases (default red bars)
- When `show_total` is enabled, a final bar displays the cumulative sum
- The chart calculates running totals automatically from the metric values

### Interactive Features
The Waterfall Chart supports these interactive behaviors:
- **Tooltips**: Hover over bars to see detailed value information
- **Legend**: When enabled, shows increase/decrease/total categories with custom labels
- **Value Labels**: When `show_value` is enabled, displays values directly on bars

## API Endpoints

- **Create Chart**: `POST /api/v1/chart/`
- **Update Chart**: `PUT /api/v1/chart/{id}`
- **Get Chart**: `GET /api/v1/chart/{id}`
- **Delete Chart**: `DELETE /api/v1/chart/{id}`
- **Get Chart Data**: `POST /api/v1/chart/data`

For complete API documentation, visit the Swagger UI at `/swagger/v1` on your Superset instance.
