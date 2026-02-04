# Time Pivot (`time_pivot`)

## Description

The Time-series Period Pivot chart compares metrics between different time periods, displaying time series data across multiple periods (like weeks or months) to show period-over-period trends and patterns. This visualization pivots time data according to a specified frequency, allowing you to see patterns that repeat at regular intervals.

This chart type is built on the NVD3 library and belongs to the "Evolution" category of visualizations.

## When to Use

Use the Time-series Period Pivot chart when you need to:

- Compare metrics across repeating time periods (e.g., compare all Mondays, all first weeks of months)
- Identify cyclical patterns or seasonality in your data
- Analyze period-over-period performance (weekly, monthly, yearly comparisons)
- Visualize time-based aggregations at specific frequencies
- Understand how a metric behaves across different time slices when pivoted by a frequency

## Example Use Cases

- **Weekly Sales Comparison**: Pivot daily sales data by week to compare each Monday across multiple weeks
- **Seasonal Analysis**: Compare metrics across the same day of the week over multiple months
- **Year-over-Year Trends**: Aggregate data at yearly intervals to see long-term patterns
- **Business Cycle Analysis**: Compare metrics at 4-week intervals to align with business reporting cycles
- **Performance Patterns**: Identify recurring performance patterns by pivoting on specific time frequencies

## Common Fields

These fields are available for all chart types when creating or updating a chart via the API.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `slice_name` | string | Yes | The name of the chart (max 250 characters) |
| `description` | string | No | A description of the chart's purpose |
| `viz_type` | string | Yes | Must be `"time_pivot"` for this chart type |
| `datasource_id` | integer | Yes | The ID of the dataset/datasource this chart uses |
| `datasource_type` | string | Yes | The type of datasource (e.g., `"table"`, `"query"`) |
| `params` | string | Yes | JSON string containing the chart configuration (see params Object below) |
| `query_context` | string | No | JSON string representing the queries needed to generate the data |
| `query_context_generation` | boolean | No | Whether the query_context is user-generated |
| `cache_timeout` | integer | No | Duration (in seconds) of the caching timeout for this chart |
| `owners` | array[integer] | No | User IDs allowed to delete or change this chart |
| `dashboards` | array[integer] | No | List of dashboard IDs to include this chart in |
| `certified_by` | string | No | Person or group that has certified this chart |
| `certification_details` | string | No | Details of the certification |
| `is_managed_externally` | boolean | No | Whether the chart is managed externally |
| `external_url` | string | No | External URL for the chart |

## params Object

The `params` field should be a JSON string containing an object with the following chart-specific properties:

### Time Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `granularity` | string | `"one day"` | Legacy time granularity (for backwards compatibility) |
| `granularity_sqla` | string | `null` | The time column to use for filtering and grouping |
| `time_grain_sqla` | string | `"P1D"` | Time grain for the visualization (e.g., `"P1D"` for 1 day, `"P1W"` for 1 week) |
| `time_range` | string | `"No filter"` | Time range filter in natural language or ISO format |

### Query Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metric` | object/string | Required | The metric to display. Can be a saved metric name or an adhoc metric object with `aggregate`, `column`, and optionally `label` |
| `adhoc_filters` | array | `[]` | List of adhoc filters to apply. Each filter has `clause` (e.g., `"WHERE"`), `subject` (column), `operator`, and `comparator` |
| `freq` | string | `"W-MON"` | The periodicity over which to pivot time. Pandas offset alias (e.g., `"AS"` for year, `"W-MON"` for week starting Monday, `"D"` for day, `"4W-MON"` for 4 weeks) |

### Chart Options

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `show_legend` | boolean | `true` | Whether to display the legend (toggles) |
| `line_interpolation` | string | `"linear"` | Line interpolation style: `"linear"`, `"basis"`, `"cardinal"`, `"monotone"`, `"step-before"`, or `"step-after"` |
| `color_picker` | object | `{r: 0, g: 122, b: 135, a: 1}` | Fixed color for the chart. Object with `r`, `g`, `b`, `a` properties |

### X-Axis Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x_axis_label` | string | `""` | Label for the X-axis |
| `x_axis_format` | string | `"SMART_NUMBER"` | D3 format string for X-axis values (e.g., `".3s"`, `",.2f"`) |
| `x_axis_showminmax` | boolean | `false` | Whether to display the min and max values of the X-axis |
| `bottom_margin` | string/integer | `"auto"` | Bottom margin in pixels, allowing for more room for axis labels. Can be `"auto"` or numeric value (50, 75, 100, 125, 150, 200) |

### Y-Axis Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `y_axis_label` | string | `""` | Label for the Y-axis |
| `y_axis_format` | string | `"SMART_NUMBER"` | D3 format string for Y-axis values (e.g., `".2f"`, `",.0f"`, `".1%"`) |
| `y_axis_showminmax` | boolean | `false` | Whether to display the min and max values of the Y-axis |
| `y_log_scale` | boolean | `false` | Use a log scale for the Y-axis |
| `y_axis_bounds` | array | `[null, null]` | Min and max bounds for the Y-axis. `[min, max]` where either can be `null` for dynamic |
| `left_margin` | string/integer | `"auto"` | Left margin in pixels, allowing for more room for axis labels. Can be `"auto"` or numeric value (50, 75, 100, 125, 150, 200) |

### Additional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `datasource` | string | Required | Datasource identifier in format `"{id}__{type}"` (e.g., `"1__table"`) |
| `viz_type` | string | `"time_pivot"` | Must be `"time_pivot"` |
| `url_params` | object | `{}` | Extra URL parameters for use in Jinja templated queries |

## Frequency Options

The `freq` parameter accepts Pandas offset aliases. Common options include:

- `"AS"` - Year (annual start)
- `"52W-MON"` - 52 weeks starting Monday
- `"W-SUN"` - 1 week starting Sunday
- `"W-MON"` - 1 week starting Monday
- `"D"` - Day
- `"4W-MON"` - 4 weeks starting Monday
- Custom Pandas offset aliases (see [Pandas documentation](https://pandas.pydata.org/pandas-docs/stable/timeseries.html#offset-aliases))

## Example Request JSON

### Creating a Time-series Period Pivot Chart

```json
{
  "slice_name": "Weekly Sales Pivot Analysis",
  "description": "Comparing weekly sales patterns by pivoting on Monday-starting weeks",
  "viz_type": "time_pivot",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{
    \"datasource\": \"1__table\",
    \"viz_type\": \"time_pivot\",
    \"granularity_sqla\": \"order_date\",
    \"time_grain_sqla\": \"P1D\",
    \"time_range\": \"Last quarter\",
    \"metric\": {
      \"aggregate\": \"SUM\",
      \"column\": {
        \"column_name\": \"sales_amount\",
        \"type\": \"DOUBLE\"
      },
      \"expressionType\": \"SIMPLE\",
      \"label\": \"Total Sales\"
    },
    \"adhoc_filters\": [
      {
        \"clause\": \"WHERE\",
        \"subject\": \"region\",
        \"operator\": \"IN\",
        \"comparator\": [\"North\", \"South\"],
        \"expressionType\": \"SIMPLE\"
      }
    ],
    \"freq\": \"W-MON\",
    \"show_legend\": true,
    \"line_interpolation\": \"linear\",
    \"x_axis_label\": \"Week Number\",
    \"x_axis_format\": \"SMART_NUMBER\",
    \"x_axis_showminmax\": false,
    \"y_axis_label\": \"Sales ($)\",
    \"y_axis_format\": \"$,.2f\",
    \"y_axis_showminmax\": true,
    \"y_log_scale\": false,
    \"y_axis_bounds\": [0, null],
    \"bottom_margin\": \"auto\",
    \"left_margin\": \"auto\",
    \"color_picker\": {
      \"r\": 0,
      \"g\": 122,
      \"b\": 135,
      \"a\": 1
    }
  }",
  "cache_timeout": 3600,
  "owners": []
}
```

### Example with Simple Metric (String Format)

```json
{
  "slice_name": "Monthly Revenue Pivot",
  "viz_type": "time_pivot",
  "datasource_id": 5,
  "datasource_type": "table",
  "params": "{
    \"datasource\": \"5__table\",
    \"viz_type\": \"time_pivot\",
    \"granularity_sqla\": \"transaction_date\",
    \"time_grain_sqla\": \"P1D\",
    \"time_range\": \"Last year\",
    \"metric\": \"sum__revenue\",
    \"adhoc_filters\": [],
    \"freq\": \"4W-MON\",
    \"show_legend\": true,
    \"line_interpolation\": \"monotone\",
    \"x_axis_label\": \"Period\",
    \"x_axis_format\": \".0f\",
    \"y_axis_label\": \"Revenue\",
    \"y_axis_format\": \"$,.0f\",
    \"y_axis_showminmax\": false,
    \"y_log_scale\": false,
    \"y_axis_bounds\": [null, null],
    \"bottom_margin\": 50,
    \"left_margin\": 75
  }"
}
```

### Example with Multiple Filters and Custom Styling

```json
{
  "slice_name": "Daily Order Volume by Week",
  "description": "Pivot daily orders to compare patterns across weeks",
  "viz_type": "time_pivot",
  "datasource_id": 10,
  "datasource_type": "table",
  "params": "{
    \"datasource\": \"10__table\",
    \"viz_type\": \"time_pivot\",
    \"granularity_sqla\": \"created_at\",
    \"time_grain_sqla\": \"PT1H\",
    \"time_range\": \"Last 2 months\",
    \"metric\": {
      \"aggregate\": \"COUNT\",
      \"column\": {
        \"column_name\": \"order_id\",
        \"type\": \"BIGINT\"
      },
      \"expressionType\": \"SIMPLE\",
      \"label\": \"Order Count\"
    },
    \"adhoc_filters\": [
      {
        \"clause\": \"WHERE\",
        \"subject\": \"status\",
        \"operator\": \"==\",
        \"comparator\": \"completed\",
        \"expressionType\": \"SIMPLE\"
      },
      {
        \"clause\": \"WHERE\",
        \"subject\": \"order_value\",
        \"operator\": \">=\",
        \"comparator\": 50,
        \"expressionType\": \"SIMPLE\"
      }
    ],
    \"freq\": \"W-SUN\",
    \"show_legend\": true,
    \"line_interpolation\": \"basis\",
    \"x_axis_label\": \"Week\",
    \"x_axis_format\": \".0f\",
    \"x_axis_showminmax\": true,
    \"y_axis_label\": \"Number of Orders\",
    \"y_axis_format\": \",.0f\",
    \"y_axis_showminmax\": true,
    \"y_log_scale\": false,
    \"y_axis_bounds\": [0, null],
    \"bottom_margin\": 100,
    \"left_margin\": 100,
    \"color_picker\": {
      \"r\": 44,
      \"g\": 160,
      \"b\": 44,
      \"a\": 1
    }
  }",
  "dashboards": [1, 5],
  "cache_timeout": 7200
}
```

## API Endpoint

To create a new chart, send a POST request to:

```
POST /api/v1/chart/
```

Include the JSON payload in the request body and ensure you have proper authentication headers.

## Notes

- The Time-series Period Pivot chart uses the legacy API (`useLegacyApi: true`)
- The `metric` field is required and cannot be cleared once set
- The `freq` parameter supports any valid Pandas offset alias for maximum flexibility
- D3 format strings are used for axis formatting - see [D3 format documentation](https://github.com/d3/d3-format) for options
- Time ranges can be specified in natural language (e.g., "Last 3 months", "Last year") or as explicit date ranges
- Axis bounds will only expand the range, not narrow it - the visualization will show at least the extent of your data
- This chart type is tagged as "Legacy" and uses the NVD3 library

## Related Chart Types

- **Time-series Line Chart**: For standard time-series visualization without pivoting
- **Time-series Bar Chart**: For time-based data with bar representation
- **Compare Chart**: For explicit period-over-period comparisons with multiple time series
