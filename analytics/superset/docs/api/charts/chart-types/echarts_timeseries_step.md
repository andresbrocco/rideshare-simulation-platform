# Stepped Line Chart (`echarts_timeseries_step`)

## Description
The Stepped Line Chart (also called step chart) is a variation of the line chart where the line forms a series of steps between data points rather than connecting them with straight diagonal lines. Each segment is rendered as a horizontal line at the value level, with vertical lines connecting different value levels. This chart type is particularly useful for showing changes that occur at irregular intervals and for visualizing data where values remain constant between measurement points, such as inventory levels, status changes, or discrete state transitions.

## When to Use
Use the Stepped Line Chart when you need to visualize data that changes in discrete steps rather than continuously. This chart type is ideal for showing values that remain constant between specific points in time and then jump to a new level. It emphasizes the duration for which a value remains constant and clearly shows the exact timing of changes, making it superior to regular line charts for representing step functions, state machines, or any data where intermediate values between measurements don't exist or aren't meaningful.

## Example Use Cases
- Tracking inventory levels over time (stock remains constant until a sale or restock occurs)
- Visualizing pricing changes where prices stay constant until explicitly updated
- Monitoring status or state transitions in systems (online/offline, active/inactive states)
- Displaying step functions in mathematics or control systems
- Showing threshold-based measurements where values only change when crossing specific thresholds
- Tracking employee headcount changes (constant between hire/termination events)
- Visualizing interest rate changes that remain constant between policy updates

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `echarts_timeseries_step` |
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
| x_axis | string | No | null | Temporal column to use as the X-axis dimension |
| time_grain_sqla | string | No | 'P1D' | Time granularity for the temporal column (e.g., 'PT1H' for hourly, 'P1D' for daily, 'P1W' for weekly, 'P1M' for monthly) |
| x_axis_force_categorical | boolean | No | false | Treat X-axis values as categorical rather than continuous |
| x_axis_sort | string | No | null | Column to sort the X-axis by. Only applies when X-axis is categorical |
| x_axis_sort_asc | boolean | No | true | Sort X-axis in ascending order (true) or descending (false) |
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
| seriesType | string | No | 'start' | Step type defining where the step appears between data points. Options: 'start', 'middle', 'end'. 'start' places the step at the beginning, 'middle' centers it, 'end' places it at the end |
| show_value | boolean | No | false | Display values on the chart |
| stack | string | No | null | Stack series on top of each other. Options: null (no stacking), 'Stack', 'Stream', 'Expand' |
| only_total | boolean | No | false | Only show total value on stacked charts (hides individual series values). Only applies when show_value and stack are both enabled |
| percentage_threshold | number | No | 0 | Minimum threshold percentage for displaying labels. Only applies when show_value and stack are enabled and only_total is disabled |
| area | boolean | No | false | Draw area under curves. Creates a filled step area chart |
| opacity | number | No | 0.2 | Area chart opacity (0-1). Also applies to confidence band. Only applies when area is enabled |
| markerEnabled | boolean | No | false | Draw a marker on data points |
| markerSize | integer | No | 6 | Size of marker (0-20). Also applies to forecast observations. Only applies when markerEnabled is true |
| zoomable | boolean | No | false | Enable data zoom controls for interactive zooming |
| minorTicks | boolean | No | false | Show minor ticks on axes |
| show_legend | boolean | No | true | Display the legend |
| legendType | string | No | 'scroll' | Legend type. Options: 'scroll', 'plain'. Only applies when show_legend is true |
| legendOrientation | string | No | 'top' | Legend position. Options: 'top', 'bottom', 'left', 'right'. Only applies when show_legend is true |
| legendMargin | integer | No | null | Additional padding for legend in pixels. Only applies when show_legend is true |
| legendSort | string | No | null | Sort legend items. Options: null (sort by data), 'asc', 'desc'. Only applies when show_legend is true |

#### X-Axis Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis_time_format | string | No | 'smart_date' | Time format for X-axis labels (e.g., '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', 'smart_date'). When using other than adaptive formatting, labels may overlap |
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
| y_axis_bounds | array | No | [null, null] | Min and max bounds for Y-axis [min, max]. Only applies when truncateYAxis is enabled |

#### Tooltip Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| rich_tooltip | boolean | No | true | Show rich tooltip with list of all series at that point in time |
| showTooltipTotal | boolean | No | true | Display total value in tooltip. Only applies when rich_tooltip is enabled |
| showTooltipPercentage | boolean | No | false | Display percentage values in tooltip. Only applies when rich_tooltip is enabled |
| tooltipSortByMetric | boolean | No | false | Sort tooltip by the selected metric in descending order. Only applies when rich_tooltip is enabled |
| tooltipTimeFormat | string | No | 'smart_date' | Time format for tooltip timestamps |

### Example Request
```json
{
  "slice_name": "Inventory Levels Over Time",
  "viz_type": "echarts_timeseries_step",
  "datasource_id": 23,
  "datasource_type": "table",
  "params": "{\"x_axis\": \"transaction_date\", \"time_grain_sqla\": \"P1D\", \"metrics\": [\"current_inventory\"], \"groupby\": [\"product_category\"], \"seriesType\": \"start\", \"area\": false, \"markerEnabled\": true, \"markerSize\": 6, \"color_scheme\": \"supersetColors\", \"show_legend\": true, \"legendType\": \"scroll\", \"legendOrientation\": \"top\", \"x_axis_time_format\": \"%b %d\", \"xAxisLabelRotation\": 45, \"y_axis_format\": \",d\", \"x_axis_title\": \"Date\", \"y_axis_title\": \"Inventory Units\", \"y_axis_title_margin\": 50, \"truncateYAxis\": false, \"rich_tooltip\": true, \"showTooltipTotal\": true, \"zoomable\": true, \"row_limit\": 10000, \"limit\": 5, \"sort_series_type\": \"sum\", \"sort_series_ascending\": false, \"adhoc_filters\": [{\"clause\": \"WHERE\", \"comparator\": \"Last 90 days\", \"expressionType\": \"SIMPLE\", \"operator\": \"TEMPORAL_RANGE\", \"subject\": \"transaction_date\"}]}",
  "description": "Step chart showing inventory levels by product category, with steps representing discrete inventory changes",
  "owners": [1],
  "cache_timeout": 3600
}
```

## Notes
- The `metrics` field is required and must contain at least one metric.
- Stepped line charts are ideal for showing discrete changes and values that remain constant between measurement points.
- The `seriesType` parameter controls where the step appears: 'start' shows the new value immediately at the time of change, 'middle' centers the transition, and 'end' delays showing the new value until the next data point.
- When `area` is enabled, the chart creates a filled step area, which can be useful for visualizing cumulative quantities like inventory or budget over time.
- The `markerEnabled` option adds visual markers at data points, which can help identify the exact timing of step changes.
- Time comparison features (`time_compare`) create additional series showing historical data for comparison.
- Forecasting requires sufficient historical data and works best with regular time intervals.
- When `x_axis_force_categorical` is true, the X-axis treats all values as discrete categories rather than continuous values.
- Advanced analytics features (rolling windows, time comparison, resampling) are applied as post-processing transformations.
- The chart supports drill-to-detail and drill-by interactive behaviors for exploring data.
- Annotation layers support Event, Formula, Interval, and Timeseries annotation types.
- The `zoomable` option adds interactive data zoom controls at the bottom of the chart for exploring specific time ranges.
- Use `opacity` to control transparency when `area` mode is enabled. Lower values (0.2-0.4) work well for overlapping areas.
- The `smart_date` format automatically adjusts date/time formatting based on the time range displayed, preventing label overlap.
- When using custom `x_axis_time_format`, consider using `xAxisLabelRotation` to prevent label overlap on dense time series.
- Stepped line charts are more appropriate than regular line charts when the data represents discrete states or levels that don't continuously transition between values.
- The chart is part of the ECharts visualization family and supports predictive analytics, advanced transformations, and is fully transformable.
