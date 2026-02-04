# Bar Chart (`echarts_timeseries_bar`)

## Description
The Bar Chart is a time-series visualization that displays metrics as vertical or horizontal bars along a temporal axis. Each bar represents a data point at a specific time interval, making it ideal for comparing values across time periods. The chart supports multiple series, stacking, advanced analytics features like forecasting and rolling windows, and rich customization options for axes, legends, and tooltips.

## When to Use
Use the Bar Chart when you need to compare discrete time-based data points, emphasize individual values rather than trends, or display categorical breakdowns over time. Bar charts are particularly effective for showing changes in fixed time intervals and highlighting differences between categories at specific points in time.

## Example Use Cases
- Monthly sales revenue comparison across different product lines
- Daily user signups by registration source over a quarter
- Quarterly budget allocation by department
- Weekly inventory levels by warehouse location
- Hourly website traffic by geographic region

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `echarts_timeseries_bar` |
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

#### Chart Orientation Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| orientation | string | No | 'vertical' | Bar orientation. Options: 'vertical', 'horizontal' |

#### Chart Title Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis_title | string | No | '' | Title for the X-axis (visible based on orientation) |
| x_axis_title_margin | integer | No | 0 | Margin between X-axis and its title in pixels. Options: 0, 15, 30, 50, 75, 100, 125, 150, 200 |
| y_axis_title | string | No | '' | Title for the Y-axis (visible based on orientation) |
| y_axis_title_margin | integer | No | 0 | Margin between Y-axis and its title in pixels. Options: 0, 15, 30, 50, 75, 100, 125, 150, 200 |
| y_axis_title_position | string | No | 'Top' | Position of Y-axis title. Options: 'Left', 'Right', 'Top', 'Bottom' |

#### Chart Options Section

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| sort_series_type | string | No | 'sum' | Method for sorting series. Options: 'name', 'sum', 'min', 'max', 'avg' |
| sort_series_ascending | boolean | No | false | Sort series in ascending order |
| color_scheme | string | No | 'supersetColors' | Color scheme for the chart |
| time_shift_color | string | No | null | Color scheme for time comparison series |
| show_value | boolean | No | false | Display values on the bars |
| stack | string | No | null | Stacking style. Options: null, 'Stack', 'Stream' |
| only_total | boolean | No | true | Only show total value on stacked charts (hides individual series values). Only applies when show_value and stack are enabled |
| percentage_threshold | number | No | 0 | Minimum threshold percentage for displaying labels on stacked bars. Only applies when show_value is enabled and only_total is disabled |
| stackDimension | string | No | null | Split stacks by a specific dimension from the groupby columns. Only applies when stack is 'Stack' |
| minorTicks | boolean | No | false | Show minor ticks on axes |
| zoomable | boolean | No | false | Enable data zoom controls for interactive zooming |
| show_legend | boolean | No | true | Display the legend |
| legendType | string | No | 'scroll' | Legend type. Options: 'scroll', 'plain'. Only applies when show_legend is true |
| legendOrientation | string | No | 'top' | Legend position. Options: 'top', 'bottom', 'left', 'right'. Only applies when show_legend is true |
| legendMargin | integer | No | null | Additional padding for legend in pixels. Only applies when show_legend is true |
| legendSort | string | No | null | Sort legend items. Options: null (sort by data), 'asc', 'desc'. Only applies when show_legend is true |

#### X-Axis Configuration

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis_time_format | string | No | 'smart_date' | Time format for X-axis labels (e.g., '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', 'smart_date'). Visible in vertical orientation |
| xAxisLabelRotation | integer | No | 0 | Rotation angle for X-axis labels in degrees (e.g., 0, 45, 90). Supports custom values. Visible in vertical orientation |
| xAxisLabelInterval | string | No | 'auto' | X-axis label display interval. Options: 'auto', '0' (show all). Visible in vertical orientation |
| y_axis_format | string | No | 'SMART_NUMBER' | Number format for Y-axis (e.g., ',d', '.2f', '.1%'). Visible in horizontal orientation |
| currency_format | object | No | null | Currency format configuration |
| logAxis | boolean | No | false | Use logarithmic scale for the axis. Visible in horizontal orientation |
| minorSplitLine | boolean | No | false | Draw split lines for minor axis ticks. Visible in horizontal orientation |
| truncateYAxis | boolean | No | false | Truncate the Y-axis. Not recommended for bar charts. Visible in horizontal orientation |
| y_axis_bounds | array | No | [null, null] | Min and max bounds for Y-axis [min, max]. Only applies when truncateYAxis is enabled. Visible in horizontal orientation |
| truncateXAxis | boolean | No | true | Truncate the X-axis. Only applicable for numerical X-axis |
| xAxisBounds | array | No | [null, null] | Min and max bounds for X-axis [min, max]. Only applies for numerical axes when truncateXAxis is enabled |
| force_max_interval | boolean | No | false | Force selected time grain as the maximum interval for X-axis labels. Only visible when time_grain_sqla is set |

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
  "slice_name": "Monthly Sales by Product Category",
  "viz_type": "echarts_timeseries_bar",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"x_axis\": \"order_date\", \"time_grain_sqla\": \"P1M\", \"metrics\": [\"sum__sales_amount\"], \"groupby\": [\"product_category\"], \"orientation\": \"vertical\", \"stack\": \"Stack\", \"show_value\": true, \"only_total\": false, \"percentage_threshold\": 5, \"color_scheme\": \"supersetColors\", \"show_legend\": true, \"legendType\": \"scroll\", \"legendOrientation\": \"top\", \"x_axis_time_format\": \"%b %Y\", \"xAxisLabelRotation\": 45, \"y_axis_format\": \"$,.0f\", \"x_axis_title\": \"Month\", \"y_axis_title\": \"Sales ($)\", \"y_axis_title_margin\": 50, \"truncateYAxis\": false, \"rich_tooltip\": true, \"showTooltipTotal\": true, \"showTooltipPercentage\": true, \"row_limit\": 10000, \"limit\": 10, \"sort_series_type\": \"sum\", \"sort_series_ascending\": false, \"adhoc_filters\": [{\"clause\": \"WHERE\", \"comparator\": \"2023\", \"expressionType\": \"SIMPLE\", \"operator\": \"TEMPORAL_RANGE\", \"subject\": \"order_date\"}]}",
  "description": "Stacked bar chart showing monthly sales by product category",
  "owners": [1],
  "cache_timeout": 3600
}
```

## Notes
- The `metrics` field is required and must contain at least one metric.
- When using `orientation: 'horizontal'`, the axes swap their roles - the temporal axis becomes the Y-axis.
- The `stack` field enables stacking behavior. Use `stackDimension` to split stacks by a specific groupby dimension.
- Time comparison features (`time_compare`) create additional series showing historical data for comparison.
- Forecasting requires sufficient historical data and works best with regular time intervals.
- The `truncateYAxis` option is not recommended for bar charts as it can misrepresent data by not showing the full scale from zero.
- When `x_axis_force_categorical` is true, the X-axis treats all values as discrete categories rather than continuous values.
- Advanced analytics features (rolling windows, time comparison, resampling) are applied as post-processing transformations.
- The chart supports drill-to-detail and drill-by interactive behaviors for exploring data.
- Annotation layers support Event, Formula, Interval, and Timeseries annotation types.
- When using `show_value` with stacking, set `only_total: false` to show values for each series; use `percentage_threshold` to hide labels below a certain percentage.
- The `zoomable` option adds interactive data zoom controls at the bottom of the chart for exploring specific time ranges.
