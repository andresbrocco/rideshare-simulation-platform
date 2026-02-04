# Mixed Timeseries (`mixed_timeseries`)

## Description
The Mixed Chart is an advanced time-series visualization that allows you to display two different data series (Query A and Query B) on the same x-axis, each with independent configuration options. This unique capability enables you to combine different chart types (e.g., bars and lines), use separate y-axes (primary and secondary), and apply distinct styling to each series. It's ideal for comparing metrics with different scales or visualizing related but distinct data patterns side by side.

## When to Use
Use the Mixed Chart when you need to compare two different metrics or data series that may have different scales, units, or optimal visualization types. This chart is particularly effective when you want to show correlation, contrast, or complementary relationships between two datasets that share a common time dimension.

## Example Use Cases
- Revenue (bars) vs. profit margin (line) over time to show volume and efficiency together
- Website traffic (line) vs. conversion rate (bars) to correlate visitor volume with success metrics
- Temperature (line on primary y-axis) vs. precipitation (bars on secondary y-axis) for weather analysis
- Sales volume (bars) vs. customer satisfaction score (line) to identify quality-quantity trade-offs
- Inventory levels (line) vs. order quantities (bars) to optimize stock management

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `mixed_timeseries` |
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

#### Shared Query Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis | string | No | null | Temporal column to use as the X-axis dimension (shared by both Query A and Query B) |
| time_grain_sqla | string | No | 'P1D' | Time granularity for the temporal column (e.g., 'PT1H' for hourly, 'P1D' for daily, 'P1W' for weekly, 'P1M' for monthly). Shared by both queries |

#### Query A Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| metrics | array | No | [] | Array of metrics to display for Query A. Can be metric names (strings) or adhoc metric objects |
| groupby | array | No | [] | Array of columns to group by for Query A, creating separate series for each group |
| adhoc_filters | array | No | [] | Array of adhoc filter objects to filter the data for Query A |
| limit | integer | No | null | Series limit for Query A - limits the number of series displayed |
| timeseries_limit_metric | object/string | No | null | Metric used to sort series when applying series limit for Query A |
| order_desc | boolean | No | true | Sort series in descending order (true) or ascending (false) for Query A |
| row_limit | integer | No | 10000 | Maximum number of rows to retrieve from the data source for Query A |
| truncate_metric | boolean | No | true | Truncate long metric names in the legend for Query A |

#### Advanced Analytics Query A Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| rolling_type | string | No | null | Rolling window function to apply for Query A. Options: null, 'None', 'mean', 'sum', 'std', 'cumsum' |
| rolling_periods | integer | No | null | Size of the rolling window in time periods for Query A. Only applies when rolling_type is set |
| min_periods | integer | No | null | Minimum number of periods required to show a rolling window value for Query A |
| time_compare | array | No | [] | Time shifts to overlay for Query A (e.g., ['1 week ago', '1 year ago']). Supports natural language like '24 hours', '7 days', '52 weeks' |
| comparison_type | string | No | 'values' | How to display time shifts for Query A. Options: 'values', 'difference', 'percentage', 'ratio' |
| resample_rule | string | No | null | Pandas resample rule for Query A (e.g., '1T' for minutely, '1H' for hourly, '1D' for daily, '1MS' for month start) |
| resample_method | string | No | null | Pandas resample method for Query A. Options: null, 'asfreq', 'zerofill', 'linear', 'ffill', 'bfill', 'median', 'mean', 'sum' |

#### Query B Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| metrics_b | array | No | [] | Array of metrics to display for Query B. Can be metric names (strings) or adhoc metric objects |
| groupby_b | array | No | [] | Array of columns to group by for Query B, creating separate series for each group |
| adhoc_filters_b | array | No | [] | Array of adhoc filter objects to filter the data for Query B |
| limit_b | integer | No | null | Series limit for Query B - limits the number of series displayed |
| timeseries_limit_metric_b | object/string | No | null | Metric used to sort series when applying series limit for Query B |
| order_desc_b | boolean | No | true | Sort series in descending order (true) or ascending (false) for Query B |
| row_limit_b | integer | No | 10000 | Maximum number of rows to retrieve from the data source for Query B |
| truncate_metric_b | boolean | No | true | Truncate long metric names in the legend for Query B |

#### Advanced Analytics Query B Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| rolling_type_b | string | No | null | Rolling window function to apply for Query B. Options: null, 'None', 'mean', 'sum', 'std', 'cumsum' |
| rolling_periods_b | integer | No | null | Size of the rolling window in time periods for Query B. Only applies when rolling_type_b is set |
| min_periods_b | integer | No | null | Minimum number of periods required to show a rolling window value for Query B |
| time_compare_b | array | No | [] | Time shifts to overlay for Query B (e.g., ['1 week ago', '1 year ago']). Supports natural language like '24 hours', '7 days', '52 weeks' |
| comparison_type_b | string | No | 'values' | How to display time shifts for Query B. Options: 'values', 'difference', 'percentage', 'ratio' |
| resample_rule_b | string | No | null | Pandas resample rule for Query B (e.g., '1T' for minutely, '1H' for hourly, '1D' for daily, '1MS' for month start) |
| resample_method_b | string | No | null | Pandas resample method for Query B. Options: null, 'asfreq', 'zerofill', 'linear', 'ffill', 'bfill', 'median', 'mean', 'sum' |

#### Annotations and Layers Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| annotation_layers | array | No | [] | Array of annotation layer configurations for adding reference lines, events, intervals, or formula-based annotations |

#### Chart Title Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis_title | string | No | '' | Title for the X-axis |
| x_axis_title_margin | integer | No | 0 | Margin between X-axis and its title in pixels. Options: 0, 15, 30, 50, 75, 100, 125, 150, 200 |
| y_axis_title | string | No | '' | Title for the primary Y-axis |
| y_axis_title_margin | integer | No | 0 | Margin between Y-axis and its title in pixels. Options: 0, 15, 30, 50, 75, 100, 125, 150, 200 |
| y_axis_title_position | string | No | 'Top' | Position of Y-axis title. Options: 'Left', 'Right', 'Top', 'Bottom' |

#### Chart Options Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| color_scheme | string | No | 'supersetColors' | Color scheme for the chart |
| time_shift_color | string | No | null | Color scheme for time comparison series |
| zoomable | boolean | No | false | Enable data zoom controls for interactive zooming |
| minorTicks | boolean | No | false | Show minor ticks on axes |
| show_legend | boolean | No | true | Display the legend |
| legendType | string | No | 'scroll' | Legend type. Options: 'scroll', 'plain'. Only applies when show_legend is true |
| legendOrientation | string | No | 'top' | Legend position. Options: 'top', 'bottom', 'left', 'right'. Only applies when show_legend is true |
| legendMargin | integer | No | null | Additional padding for legend in pixels. Only applies when show_legend is true |
| legendSort | string | No | null | Sort legend items. Options: null (sort by data), 'asc', 'desc'. Only applies when show_legend is true |

#### Query A Customization

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| seriesType | string | No | 'line' | Series chart type for Query A. Options: 'line', 'scatter', 'smooth' (smooth line), 'bar', 'start' (step-start), 'middle' (step-middle), 'end' (step-end) |
| stack | boolean | No | false | Stack series on top of each other for Query A |
| area | boolean | No | false | Draw area under curves for Query A. Only applicable for line types |
| show_value | boolean | No | false | Display numerical values on data points for Query A |
| only_total | boolean | No | true | Only show total value on stacked charts for Query A (hides individual series values). Only applies when show_value and stack are enabled |
| opacity | number | No | 0.2 | Opacity of area chart for Query A (0.0-1.0) |
| markerEnabled | boolean | No | false | Draw markers on data points for Query A. Only applicable for line types |
| markerSize | number | No | 6 | Size of markers for Query A (0-100). Also applies to forecast observations |
| yAxisIndex | integer | No | 0 | Y-axis assignment for Query A. Options: 0 (Primary), 1 (Secondary) |
| sort_series_type | string | No | 'sum' | Method for sorting series for Query A. Options: 'name', 'sum', 'min', 'max', 'avg' |
| sort_series_ascending | boolean | No | false | Sort series in ascending order for Query A |

#### Query B Customization

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| seriesTypeB | string | No | 'line' | Series chart type for Query B. Options: 'line', 'scatter', 'smooth' (smooth line), 'bar', 'start' (step-start), 'middle' (step-middle), 'end' (step-end) |
| stackB | boolean | No | false | Stack series on top of each other for Query B |
| areaB | boolean | No | false | Draw area under curves for Query B. Only applicable for line types |
| show_valueB | boolean | No | false | Display numerical values on data points for Query B |
| only_totalB | boolean | No | true | Only show total value on stacked charts for Query B (hides individual series values). Only applies when show_valueB and stackB are enabled |
| opacityB | number | No | 0.2 | Opacity of area chart for Query B (0.0-1.0) |
| markerEnabledB | boolean | No | false | Draw markers on data points for Query B. Only applicable for line types |
| markerSizeB | number | No | 6 | Size of markers for Query B (0-100). Also applies to forecast observations |
| yAxisIndexB | integer | No | 0 | Y-axis assignment for Query B. Options: 0 (Primary), 1 (Secondary) |
| sort_series_typeB | string | No | 'sum' | Method for sorting series for Query B. Options: 'name', 'sum', 'min', 'max', 'avg' |
| sort_series_ascendingB | boolean | No | false | Sort series in ascending order for Query B |

#### X-Axis Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis_time_format | string | No | 'smart_date' | Time format for X-axis labels (e.g., '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', 'smart_date') |
| xAxisLabelRotation | integer | No | 0 | Rotation angle for X-axis labels in degrees (e.g., 0, 45, 90). Supports custom values |
| xAxisLabelInterval | string | No | 'auto' | X-axis label display interval. Options: 'auto', '0' (show all) |
| force_max_interval | boolean | No | false | Force selected time grain as the maximum interval for X-axis labels. Only visible when time_grain_sqla is set |
| truncateXAxis | boolean | No | true | Truncate the X-axis. Only applicable for numerical X-axis |
| xAxisBounds | array | No | [null, null] | Min and max bounds for X-axis [min, max]. Only applies for numerical axes when truncateXAxis is enabled |

#### Tooltip Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| show_query_identifiers | boolean | No | false | Add Query A and Query B identifiers to tooltips to help differentiate series |
| rich_tooltip | boolean | No | true | Show rich tooltip with list of all series at that point in time |
| showTooltipTotal | boolean | No | true | Display total value in tooltip. Only applies when rich_tooltip is enabled |
| showTooltipPercentage | boolean | No | false | Display percentage values in tooltip. Only applies when rich_tooltip is enabled |
| tooltipSortByMetric | boolean | No | false | Sort tooltip by the selected metric in descending order. Only applies when rich_tooltip is enabled |
| tooltipTimeFormat | string | No | 'smart_date' | Time format for tooltip timestamps |

#### Y-Axis Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| minorSplitLine | boolean | No | false | Draw split lines for minor y-axis ticks |
| truncateYAxis | boolean | No | false | Truncate the primary Y-axis. Can be overridden by specifying min or max bounds |
| y_axis_bounds | array | No | [null, null] | Min and max bounds for primary Y-axis [min, max]. When left empty, bounds are dynamically defined. Note: this feature will only expand the axis range, not narrow it |
| y_axis_format | string | No | 'SMART_NUMBER' | Number format for primary Y-axis (e.g., ',d', '.2f', '.1%') |
| currency_format | object | No | null | Currency format configuration for primary Y-axis |
| logAxis | boolean | No | false | Use logarithmic scale on primary y-axis |
| y_axis_bounds_secondary | array | No | [null, null] | Min and max bounds for secondary Y-axis [min, max]. Only works when Independent Y-axis bounds are enabled. When left empty, bounds are dynamically defined. Note: this feature will only expand the axis range, not narrow it |
| y_axis_format_secondary | string | No | 'SMART_NUMBER' | Number format for secondary Y-axis (e.g., ',d', '.2f', '.1%') |
| currency_format_secondary | object | No | null | Currency format configuration for secondary Y-axis |
| yAxisTitleSecondary | string | No | '' | Title for the secondary y-axis |
| logAxisSecondary | boolean | No | false | Use logarithmic scale on secondary y-axis |

### Example Request
```json
{
  "slice_name": "Revenue vs Profit Margin Analysis",
  "viz_type": "mixed_timeseries",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"x_axis\": \"order_date\", \"time_grain_sqla\": \"P1M\", \"metrics\": [\"sum__revenue\"], \"groupby\": [], \"seriesType\": \"bar\", \"area\": false, \"stack\": false, \"yAxisIndex\": 0, \"show_value\": false, \"opacity\": 0.2, \"markerEnabled\": false, \"markerSize\": 6, \"sort_series_type\": \"sum\", \"sort_series_ascending\": false, \"metrics_b\": [{\"aggregate\": \"AVG\", \"column\": {\"column_name\": \"profit_margin\"}, \"expressionType\": \"SIMPLE\", \"label\": \"Avg Profit Margin\"}], \"groupby_b\": [], \"seriesTypeB\": \"line\", \"areaB\": false, \"stackB\": false, \"yAxisIndexB\": 1, \"show_valueB\": true, \"opacityB\": 0.2, \"markerEnabledB\": true, \"markerSizeB\": 8, \"sort_series_typeB\": \"sum\", \"sort_series_ascendingB\": false, \"show_query_identifiers\": true, \"color_scheme\": \"supersetColors\", \"show_legend\": true, \"legendType\": \"scroll\", \"legendOrientation\": \"top\", \"x_axis_time_format\": \"%b %Y\", \"xAxisLabelRotation\": 45, \"y_axis_format\": \"$,.0f\", \"y_axis_format_secondary\": \".1%\", \"x_axis_title\": \"Month\", \"y_axis_title\": \"Revenue ($)\", \"yAxisTitleSecondary\": \"Profit Margin (%)\", \"y_axis_title_margin\": 50, \"truncateYAxis\": false, \"rich_tooltip\": true, \"showTooltipTotal\": true, \"row_limit\": 10000, \"row_limit_b\": 10000, \"adhoc_filters\": [{\"clause\": \"WHERE\", \"comparator\": \"2023\", \"expressionType\": \"SIMPLE\", \"operator\": \"TEMPORAL_RANGE\", \"subject\": \"order_date\"}]}",
  "description": "Mixed chart showing monthly revenue (bars on primary axis) and profit margin percentage (line on secondary axis)",
  "owners": [1],
  "cache_timeout": 3600
}
```

## Notes
- The Mixed Chart uses two independent queries (Query A and Query B), each with its own metrics, groupby columns, filters, and advanced analytics settings.
- Both queries share the same x-axis (temporal column) and time granularity.
- Each query can be displayed using a different chart type (line, bar, scatter, smooth line, or step variants) via `seriesType` and `seriesTypeB`.
- Each query can be assigned to either the primary (0) or secondary (1) y-axis via `yAxisIndex` and `yAxisIndexB`, allowing comparison of metrics with different scales.
- The `show_query_identifiers` option adds "Query A" and "Query B" labels to tooltip entries, making it easier to distinguish between the two data sources.
- Advanced analytics features (rolling windows, time comparison, resampling) can be configured independently for each query.
- The chart supports drill-to-detail and drill-by interactive behaviors for exploring data.
- Annotation layers support Event, Formula, Interval, and Timeseries annotation types.
- The `zoomable` option adds interactive data zoom controls at the bottom of the chart for exploring specific time ranges.
- When using different y-axis assignments, configure appropriate formats and bounds for both the primary and secondary y-axes.
- The chart supports 2 query objects (queryObjectCount: 2), making it more resource-intensive than single-query charts.
- Series from both queries appear in the same legend and can be sorted independently using their respective sort controls.
