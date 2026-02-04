# Scatter Plot (`echarts_timeseries_scatter`)

## Description
The Scatter Plot is a time-series visualization that displays data points as individual markers without connecting lines. The horizontal axis uses linear units, and points are displayed in order, making it ideal for showing the statistical relationship between two variables. Unlike traditional line charts, scatter plots emphasize individual data points rather than trends, making them excellent for identifying patterns, correlations, and outliers in time-series data.

## When to Use
Use the Scatter Plot when you need to visualize the distribution of individual data points over time, identify correlations between variables, or detect outliers and anomalies. Scatter plots are particularly effective when you want to see the density and spread of data points rather than focusing on continuous trends. They excel at revealing patterns in noisy data where line charts might obscure individual observations.

## Example Use Cases
- Analyzing sensor data or IoT measurements to identify anomalies or outliers over time
- Visualizing stock trading volumes at specific price points throughout the day
- Examining the relationship between temperature and energy consumption across different time periods
- Detecting patterns in server response times or latency measurements over time
- Studying customer purchase behavior by showing transaction amounts over time
- Monitoring quality control metrics where individual measurements matter more than trends

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `echarts_timeseries_scatter` |
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
The `params` field should contain a JSON-encoded string with the following properties:

#### Query Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis | string | No | null | Temporal or numerical column to use as the X-axis dimension |
| time_grain_sqla | string | No | 'P1D' | Time granularity for temporal columns (e.g., 'PT1H' for hourly, 'P1D' for daily, 'P1W' for weekly, 'P1M' for monthly) |
| x_axis_sort | string | No | null | Column to sort the X-axis by. Only applies when X-axis is categorical |
| x_axis_sort_asc | boolean | No | true | Sort X-axis in ascending order (true) or descending (false) |
| x_axis_force_categorical | boolean | No | false | Treat X-axis values as categorical rather than continuous |
| metrics | array | Yes | - | Array of metrics to display. Can be metric names (strings) or adhoc metric objects. Required field |
| groupby | array | No | [] | Array of columns to group by, creating separate series for each group |
| contributionMode | string | No | null | Calculate contribution to row total. Options: null, 'row' |
| adhoc_filters | array | No | [] | Array of adhoc filter objects to filter the data |
| limit | integer | No | null | Series limit - limits the number of series displayed |
| group_others_when_limit_reached | boolean | No | false | Group remaining series as "Others" when series limit is reached |
| timeseries_limit_metric | object/string | No | null | Metric used to sort series when applying series limit |
| order_desc | boolean | No | true | Sort series in descending order (true) or ascending (false) |
| row_limit | integer | No | 10000 | Maximum number of rows to retrieve from the data source |
| truncate_metric | boolean | No | true | Truncate long metric names in the legend |
| show_empty_columns | boolean | No | true | Show columns with no data |

#### Advanced Analytics Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| rolling_type | string | No | null | Rolling window function to apply. Options: null, 'None', 'mean', 'sum', 'std', 'cumsum' |
| rolling_periods | integer | No | null | Size of the rolling window in time periods. Only applies when rolling_type is set |
| min_periods | integer | No | null | Minimum number of periods required to show a rolling window value |
| time_compare | array | No | [] | Time shifts to overlay (e.g., ['1 week ago', '1 year ago']). Supports natural language like '24 hours', '7 days', '52 weeks' |
| comparison_type | string | No | 'values' | How to display time shifts. Options: 'values', 'difference', 'percentage', 'ratio' |
| resample_rule | string | No | null | Pandas resample rule (e.g., '1T' for minutely, '1H' for hourly, '1D' for daily, '1MS' for month start) |
| resample_method | string | No | null | Pandas resample method. Options: null, 'asfreq', 'zerofill', 'linear', 'ffill', 'bfill', 'median', 'mean', 'sum' |

#### Annotations and Layers Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| annotation_layers | array | No | [] | Array of annotation layer configurations for adding reference lines, events, intervals, or formula-based annotations |

#### Predictive Analytics Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| forecastEnabled | boolean | No | false | Enable forecasting using Prophet algorithm |
| forecastPeriods | integer | No | 10 | Number of periods to forecast into the future |
| forecastInterval | number | No | 0.8 | Confidence interval width for forecast (between 0 and 1) |
| forecastSeasonalityYearly | boolean/string | No | null | Apply yearly seasonality. Options: null (default), true, false, or integer for Fourier order |
| forecastSeasonalityWeekly | boolean/string | No | null | Apply weekly seasonality. Options: null (default), true, false, or integer for Fourier order |
| forecastSeasonalityDaily | boolean/string | No | null | Apply daily seasonality. Options: null (default), true, false, or integer for Fourier order |

#### Chart Title Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis_title | string | No | '' | Title for the X-axis |
| x_axis_title_margin | integer | No | 0 | Margin between X-axis and its title in pixels. Options: 0, 15, 30, 50, 75, 100, 125, 150, 200 |
| y_axis_title | string | No | '' | Title for the Y-axis |
| y_axis_title_margin | integer | No | 0 | Margin between Y-axis and its title in pixels. Options: 0, 15, 30, 50, 75, 100, 125, 150, 200 |
| y_axis_title_position | string | No | 'Top' | Position of Y-axis title. Options: 'Left', 'Right', 'Top', 'Bottom' |

#### Chart Options Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| sort_series_type | string | No | 'sum' | Method for sorting series. Options: 'name', 'sum', 'min', 'max', 'avg' |
| sort_series_ascending | boolean | No | false | Sort series in ascending order |
| color_scheme | string | No | 'supersetColors' | Color scheme for the chart |
| time_shift_color | string | No | null | Color scheme for time comparison series |
| show_value | boolean | No | false | Display values on the chart |
| only_total | boolean | No | false | Only show total value when displaying values (hides individual series values) |
| percentage_threshold | number | No | 0 | Minimum threshold percentage for displaying labels. Only applies when show_value is enabled |
| markerEnabled | boolean | No | false | Draw markers on data points. For scatter plots, this controls marker visibility |
| markerSize | integer | No | 6 | Size of marker (0-100). Also applies to forecast observations |
| zoomable | boolean | No | false | Enable data zoom controls for interactive zooming |
| minorTicks | boolean | No | false | Show minor ticks on axes |
| show_legend | boolean | No | true | Display the legend |
| legendType | string | No | 'scroll' | Legend type. Options: 'scroll', 'plain'. Only applies when show_legend is true |
| legendOrientation | string | No | 'top' | Legend position. Options: 'top', 'bottom', 'left', 'right'. Only applies when show_legend is true |
| legendMargin | integer | No | null | Additional padding for legend in pixels. Only applies when show_legend is true |

#### X-Axis Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis_time_format | string | No | 'smart_date' | Time format for X-axis labels when X-axis is temporal (e.g., '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', 'smart_date'). Only applies when X-axis column is a time type. When using other than adaptive formatting, labels may overlap |
| x_axis_number_format | string | No | 'SMART_NUMBER' | Number format for X-axis labels when X-axis is numeric (e.g., ',d', '.2f', 'SMART_NUMBER'). Only applies when X-axis column is a floating-point type (FLOAT, DOUBLE, REAL, NUMERIC, DECIMAL) |
| xAxisLabelRotation | integer | No | 0 | Rotation angle for X-axis labels in degrees (e.g., 0, 45, 90). Supports custom values |
| xAxisLabelInterval | string | No | 'auto' | X-axis label display interval. Options: 'auto', '0' (show all) |
| force_max_interval | boolean | No | false | Forces selected time grain as the maximum interval for X-axis labels. Only visible when time_grain_sqla is set |
| truncateXAxis | boolean | No | true | Truncate the X-axis. Only applicable for numerical X-axis |
| xAxisBounds | array | No | [null, null] | Min and max bounds for X-axis [min, max]. Only applies for numerical axes when truncateXAxis is enabled |

#### Y-Axis Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| y_axis_format | string | No | 'SMART_NUMBER' | Number format for Y-axis (e.g., ',d', '.2f', '.1%', 'SMART_NUMBER') |
| currency_format | object | No | null | Currency format configuration |
| logAxis | boolean | No | false | Use logarithmic scale for Y-axis |
| minorSplitLine | boolean | No | false | Draw split lines for minor Y-axis ticks |
| truncateYAxis | boolean | No | false | Truncate Y-axis. Can be overridden by specifying a min or max bound |
| y_axis_bounds | array | No | [null, null] | Min and max bounds for Y-axis [min, max]. Only applies when truncateYAxis is enabled. When left empty, the bounds are dynamically defined based on the min/max of the data. This feature expands the axis range but won't narrow the data's extent |

#### Tooltip Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| rich_tooltip | boolean | No | true | Show rich tooltip with list of all series at that point in time |
| showTooltipTotal | boolean | No | true | Display total value in tooltip. Only applies when rich_tooltip is enabled |
| showTooltipPercentage | boolean | No | false | Display percentage values in tooltip. Only applies when rich_tooltip is enabled |
| tooltipSortByMetric | boolean | No | false | Sort tooltip by the selected metric in descending order. Only applies when rich_tooltip is enabled |
| tooltipTimeFormat | string | No | 'smart_date' | Time format for tooltip timestamps |

### Metric Object Format
Metrics can be specified as either:

**Simple string format** (for saved metrics):
```json
"COUNT(*)"
```

**Adhoc metric object** (for custom aggregations):
```json
{
  "expressionType": "SIMPLE",
  "column": {
    "column_name": "response_time",
    "type": "DOUBLE"
  },
  "aggregate": "AVG",
  "label": "Avg Response Time"
}
```

Or for SQL expression:
```json
{
  "expressionType": "SQL",
  "sqlExpression": "PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time)",
  "label": "P95 Response Time"
}
```

### Filter Object Format
Adhoc filters follow this structure:
```json
{
  "clause": "WHERE",
  "subject": "column_name",
  "operator": ">=",
  "comparator": 100,
  "expressionType": "SIMPLE"
}
```

For temporal filters:
```json
{
  "clause": "WHERE",
  "subject": "timestamp_column",
  "operator": "TEMPORAL_RANGE",
  "comparator": "Last 7 days",
  "expressionType": "SIMPLE"
}
```

### Example Request
```json
{
  "slice_name": "Server Response Time Distribution",
  "viz_type": "echarts_timeseries_scatter",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"x_axis\": \"request_timestamp\", \"time_grain_sqla\": \"PT1H\", \"metrics\": [{\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"response_time_ms\", \"type\": \"DOUBLE\"}, \"aggregate\": \"AVG\", \"label\": \"Avg Response Time\"}], \"groupby\": [\"server_region\"], \"markerEnabled\": true, \"markerSize\": 8, \"color_scheme\": \"supersetColors\", \"show_legend\": true, \"legendType\": \"scroll\", \"legendOrientation\": \"top\", \"x_axis_time_format\": \"%b %d %H:%M\", \"xAxisLabelRotation\": 45, \"y_axis_format\": \",d\", \"x_axis_title\": \"Time\", \"y_axis_title\": \"Response Time (ms)\", \"y_axis_title_margin\": 50, \"truncateYAxis\": false, \"rich_tooltip\": true, \"showTooltipTotal\": false, \"zoomable\": true, \"row_limit\": 10000, \"adhoc_filters\": [{\"clause\": \"WHERE\", \"comparator\": \"Last 24 hours\", \"expressionType\": \"SIMPLE\", \"operator\": \"TEMPORAL_RANGE\", \"subject\": \"request_timestamp\"}]}",
  "description": "Scatter plot showing server response time distribution by region over the last 24 hours",
  "owners": [1],
  "cache_timeout": 300
}
```

## Notes
- The `metrics` field is required and must contain at least one metric.
- Scatter plots display individual data points without connecting lines, making them ideal for showing data distribution and identifying outliers.
- The chart supports both temporal and numerical X-axes, with conditional formatting options based on the column type.
- When the X-axis is a time column, use `x_axis_time_format` for formatting. When it's numeric, use `x_axis_number_format`.
- The `markerEnabled` and `markerSize` properties control the appearance of scatter points. Unlike line charts where markers are optional, scatter plots rely on markers as the primary visual element.
- Time comparison features (`time_compare`) create additional series showing historical data for comparison.
- Forecasting requires sufficient historical data and works best with regular time intervals.
- When `x_axis_force_categorical` is true, the X-axis treats all values as discrete categories rather than continuous values.
- Advanced analytics features (rolling windows, time comparison, resampling) are applied as post-processing transformations.
- The chart supports drill-to-detail and drill-by interactive behaviors for exploring data.
- Annotation layers support Event, Formula, Interval, and Timeseries annotation types.
- The `zoomable` option adds interactive data zoom controls at the bottom of the chart for exploring specific time ranges.
- The `smart_date` format automatically adjusts date/time formatting based on the time range displayed, preventing label overlap.
- When using custom `x_axis_time_format`, consider using `xAxisLabelRotation` to prevent label overlap on dense time series.
- Scatter plots excel at revealing patterns in noisy data where continuous lines might obscure individual observations.
- For better visibility of overlapping points, adjust the `markerSize` property. Smaller markers work well for dense data, while larger markers are better for sparse data.
- The logarithmic Y-axis (`logAxis`) is particularly useful for scatter plots showing data that spans multiple orders of magnitude.
