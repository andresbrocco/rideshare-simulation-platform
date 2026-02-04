# Compare Chart (`compare`)

## Description

The Compare chart (also known as Time-series Percent Change) visualizes multiple time-series objects in a single chart, allowing you to compare trends and percent changes across different time periods or series. This chart displays data as line graphs with configurable axes, annotations, and advanced analytics capabilities. Note: This chart is deprecated and the Time-series Chart is recommended as a replacement.

## When to Use

Use the Compare chart when you need to visualize and compare multiple time-series metrics or dimensions simultaneously on a single chart with percent change calculations. This visualization is particularly useful for tracking trends over time and comparing historical performance across different periods using advanced analytical features like rolling windows and time shifts.

## Example Use Cases

- Comparing sales revenue growth across different product categories over time
- Analyzing website traffic percent changes between different marketing campaigns
- Tracking year-over-year performance metrics with time shift comparisons
- Monitoring multiple KPIs with rolling average calculations to smooth out fluctuations
- Visualizing seasonal trends with time comparison overlays showing previous periods

## Request Format

### Common Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `compare` |
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

The `params` field must be a JSON string containing an object with the following fields:

#### Time Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| granularity | string | No | "one day" | Time granularity for the visualization. Supports natural language (e.g., "10 seconds", "1 day", "56 weeks") or ISO 8601 periods (e.g., "PT5S", "P1D", "P1W") |
| granularity_sqla | string | No | null | The time column for the visualization. Can be an arbitrary expression that returns a DATETIME column |
| time_grain_sqla | string | No | "P1D" | Time grain for the visualization. The grain is the time interval represented by a single point on the chart. Choices depend on datasource configuration |
| time_range | string | No | "No filter" | Time range filter. Supports relative times (e.g., "Last month", "Last 7 days", "now") evaluated on the server using server's local time. All timestamps are in UTC and evaluated by the database using the engine's local timezone |

#### Query Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| metrics | array | Yes | [] | List of metrics to display. Each metric can be a saved metric name or an adhoc metric object with aggregation function and column |
| adhoc_filters | array | No | [] | List of adhoc filters to apply to the query. Each filter can specify column, operator, and comparison value |
| groupby | array | No | [] | List of column names to group by. Each series is represented by a specific color in the chart |
| limit | integer | No | null | Series limit. Limits the number of series that get displayed using a joined subquery. Useful when grouping by high cardinality columns |
| timeseries_limit_metric | object/string | No | null | Metric to use for sorting the query results. Determines what data are truncated if a series or row limit is reached |
| order_desc | boolean | No | true | If enabled, sorts results descending; otherwise sorts ascending. Only visible when timeseries_limit_metric is set |
| contribution | boolean | No | false | Compute the contribution to the total for each series |
| row_limit | integer | No | 10000 | Limits the number of rows computed in the query. Choices: 10, 50, 100, 250, 500, 1000, 5000, 10000, 50000 |

#### Chart Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| color_scheme | string | No | "supersetColors" | The color scheme for rendering the chart. Available schemes depend on categorical color scheme registry |

#### X Axis Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis_label | string | No | "" | Label for the X axis |
| bottom_margin | string/integer | No | "auto" | Bottom margin in pixels, allowing for more room for axis labels. Options: "auto", 50, 75, 100, 125, 150, 200 |
| x_ticks_layout | string | No | "auto" | The way the ticks are laid out on the X-axis. Options: "auto", "flat", "45°", "staggered" |
| x_axis_format | string | No | "smart_date" | X axis format using D3 time format specifiers |
| x_axis_showminmax | boolean | No | false | Whether to display the min and max values of the X-axis |

#### Y Axis Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| y_axis_label | string | No | "" | Label for the Y axis |
| left_margin | string/integer | No | "auto" | Left margin in pixels, allowing for more room for axis labels. Options: "auto", 50, 75, 100, 125, 150, 200 |
| y_axis_showminmax | boolean | No | false | Whether to display the min and max values of the Y-axis (Y bounds) |
| y_log_scale | boolean | No | false | Use a log scale for the Y-axis |
| y_axis_format | string | No | "SMART_NUMBER" | Y axis format using D3 format specifiers |
| y_axis_bounds | array | No | [null, null] | Bounds for the Y-axis as [min, max]. When left empty, bounds are dynamically defined based on min/max of data. This feature only expands the axis range, it won't narrow the data's extent |

#### Advanced Analytics

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| rolling_type | string | No | "None" | Rolling window function to apply. Options: "None", "mean", "sum", "std", "cumsum". Works with rolling_periods |
| rolling_periods | integer | No | null | Size of the rolling window function, relative to the time granularity selected |
| min_periods | integer | No | null | Minimum number of rolling periods required to show a value. Hides the "ramp up" period |
| time_compare | array | No | [] | Overlay one or more timeseries from relative time periods. Examples: "1 day", "1 week", "28 days", "30 days", "52 weeks", "1 year". Supports free text natural language |
| comparison_type | string | No | "values" | How to display time shifts. Options: "values" (Actual Values), "absolute" (Difference), "percentage" (Percentage change), "ratio" (Ratio) |
| resample_rule | string | No | null | Pandas resample rule. Options: "1T", "1H", "1D", "7D", "1M", "1AS" |
| resample_method | string | No | null | Pandas resample method. Options: "asfreq", "bfill", "ffill", "median", "mean", "sum" |

#### Annotations

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| annotation_layers | array | No | [] | List of annotation layer configurations to overlay on the chart |

### Example Request

```json
{
  "slice_name": "Revenue Growth Comparison",
  "viz_type": "compare",
  "datasource_id": 123,
  "datasource_type": "table",
  "description": "Comparing revenue growth across product categories with year-over-year comparison",
  "params": "{\"metrics\":[\"revenue\"],\"groupby\":[\"product_category\"],\"granularity_sqla\":\"order_date\",\"time_grain_sqla\":\"P1D\",\"time_range\":\"Last year\",\"color_scheme\":\"supersetColors\",\"x_axis_label\":\"Date\",\"y_axis_label\":\"Revenue ($)\",\"y_axis_format\":\"$,.2f\",\"x_axis_format\":\"smart_date\",\"bottom_margin\":\"auto\",\"left_margin\":\"auto\",\"x_ticks_layout\":\"auto\",\"x_axis_showminmax\":false,\"y_axis_showminmax\":false,\"y_log_scale\":false,\"y_axis_bounds\":[null,null],\"rolling_type\":\"mean\",\"rolling_periods\":7,\"min_periods\":7,\"time_compare\":[\"1 year\"],\"comparison_type\":\"percentage\",\"contribution\":false,\"order_desc\":true,\"limit\":10,\"row_limit\":10000,\"adhoc_filters\":[],\"annotation_layers\":[]}",
  "cache_timeout": 3600,
  "owners": [1],
  "dashboards": [456]
}
```

### Example params JSON (formatted)

```json
{
  "metrics": ["revenue"],
  "groupby": ["product_category"],
  "granularity_sqla": "order_date",
  "time_grain_sqla": "P1D",
  "time_range": "Last year",
  "color_scheme": "supersetColors",
  "x_axis_label": "Date",
  "y_axis_label": "Revenue ($)",
  "y_axis_format": "$,.2f",
  "x_axis_format": "smart_date",
  "bottom_margin": "auto",
  "left_margin": "auto",
  "x_ticks_layout": "auto",
  "x_axis_showminmax": false,
  "y_axis_showminmax": false,
  "y_log_scale": false,
  "y_axis_bounds": [null, null],
  "rolling_type": "mean",
  "rolling_periods": 7,
  "min_periods": 7,
  "time_compare": ["1 year"],
  "comparison_type": "percentage",
  "contribution": false,
  "order_desc": true,
  "limit": 10,
  "row_limit": 10000,
  "adhoc_filters": [],
  "annotation_layers": []
}
```

## Notes

- **Deprecated**: This chart type is deprecated. The Time-series Chart is recommended as a replacement with enhanced features and better performance.
- **Legacy API**: This chart uses the legacy API (`useLegacyApi: true`), which may have different behavior compared to newer chart types.
- **Category**: This chart belongs to the "Evolution" category and is tagged with: Legacy, Time, nvd3, Advanced-Analytics, Comparison, Line, Percentages, Predictive, Trend.
- **Metrics Format**: Metrics can be specified as simple strings (for saved metrics) or as adhoc metric objects with structure: `{"expressionType": "SIMPLE", "column": {"column_name": "..."}, "aggregate": "SUM", "label": "..."}`
- **Time Format**: All time-related filters are evaluated on the server in the server's local timezone. Timestamps in tooltips are shown in UTC.
- **Advanced Analytics**: The chart supports sophisticated analytical features including rolling windows, time comparisons, and resampling for detailed trend analysis.
