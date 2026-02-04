# Area Chart (`echarts_area`)

## Description
The Area Chart is a time-series visualization that displays quantitative data over a continuous time interval. It combines line chart elements with filled areas beneath the lines, making it effective for showing cumulative totals and the magnitude of change over time. Multiple series can be stacked on top of each other to show part-to-whole relationships.

## When to Use
Area charts are ideal when you need to emphasize the magnitude of change over time and show trends in data. They work particularly well when displaying cumulative values or when you want to show how multiple data series contribute to a total. The filled area provides a strong visual emphasis on the volume of data, making trends and patterns more apparent than simple line charts.

## Example Use Cases
- Tracking website traffic or user engagement metrics over time, with different areas representing different traffic sources
- Visualizing sales revenue across multiple product categories over fiscal quarters, showing both individual and cumulative performance
- Monitoring resource consumption (CPU, memory, bandwidth) across multiple servers or services over time
- Displaying inventory levels for different product lines throughout the year
- Analyzing population growth across different demographic segments over decades

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `echarts_area` |
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
The `params` field must be a JSON string containing the following fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis | string | No | null | Name of temporal column used for x-axis. For time-series data, this is the time column |
| time_grain_sqla | string | No | null | Time granularity for temporal aggregation (e.g., 'P1D' for daily, 'P1W' for weekly, 'P1M' for monthly) |
| forceCategorical | boolean | No | false | Make the x-axis categorical instead of continuous |
| x_axis_sort | string | No | null | Column to sort x-axis by |
| x_axis_sort_asc | boolean | No | true | Sort x-axis in ascending order |
| metrics | array | Yes | [] | List of metrics to display. Can be strings (datasource metric names) or ad-hoc metric objects |
| groupby | array | No | [] | List of columns to group by. Creates separate series for each unique combination |
| contributionMode | string | No | null | Show values as contribution to total. Options: 'row', 'column', null |
| adhoc_filters | array | No | [] | List of ad-hoc filter objects to apply to the query |
| limit | integer | No | null | Maximum number of series to display |
| group_others_when_limit_reached | boolean | No | false | When true, groups remaining series into an 'Others' category when series limit is reached |
| timeseries_limit_metric | object/string | No | null | Metric used to determine which series to keep when limit is applied |
| order_desc | boolean | No | true | Sort series in descending order |
| row_limit | integer | No | 10000 | Maximum number of rows to retrieve from datasource |
| truncate_metric | boolean | No | true | Truncate long metric names in the legend |
| show_empty_columns | boolean | No | false | Show columns with no data |
| sort_series_type | string | No | 'sum' | How to sort series. Options: 'name', 'sum', 'min', 'max', 'avg' |
| sort_series_ascending | boolean | No | false | Sort series in ascending order |
| color_scheme | string | No | 'supersetColors' | Color scheme to use for the chart |
| time_shift_color | string | No | null | Color scheme for time-shifted series |
| seriesType | string | No | 'line' | Series line style. Options: 'line', 'smooth', 'start', 'middle', 'end' (step types) |
| opacity | number | No | 0.2 | Area chart opacity (0-1). Also applies to confidence band |
| show_value | boolean | No | false | Show series values on the chart |
| stack | string | No | null | Stacking style. Options: null (none), 'Stack', 'Stream', 'Expand' |
| only_total | boolean | No | false | Only show the total value on stacked chart, not individual category values |
| percentage_threshold | number | No | 0 | Minimum threshold in percentage points for showing labels (when show_value is true and stack is enabled) |
| show_extra_controls | boolean | No | false | Whether to show extra controls |
| markerEnabled | boolean | No | false | Draw markers on data points. Only applicable for line types |
| markerSize | number | No | 6 | Size of marker (0-20). Also applies to forecast observations |
| minorTicks | boolean | No | false | Show minor ticks on axes |
| zoomable | boolean | No | false | Enable data zoom controls for the chart |
| show_legend | boolean | No | true | Whether to display a legend for the chart |
| legendType | string | No | 'scroll' | Legend type. Options: 'scroll', 'plain' |
| legendOrientation | string | No | 'top' | Legend position. Options: 'top', 'bottom', 'left', 'right' |
| legendMargin | integer | No | null | Additional padding for legend |
| legendSort | string | No | null | Sort legend items. Options: 'asc' (label ascending), 'desc' (label descending), null (sort by data) |
| x_axis_time_format | string | No | 'smart_date' | D3 time format string for x-axis labels |
| xAxisLabelRotation | integer | No | 0 | Rotation angle for x-axis labels (0, 45, 90, or custom degrees) |
| xAxisLabelInterval | string | No | 'auto' | X-axis label interval. Options: 'auto', '0' (show all) |
| force_max_interval | boolean | No | false | Forces selected time grain as the maximum interval for x-axis labels |
| rich_tooltip | boolean | No | true | Shows a list of all series available at that point in time |
| showTooltipTotal | boolean | No | true | Whether to display the total value in the tooltip |
| showTooltipPercentage | boolean | No | false | Whether to display the percentage value in the tooltip |
| tooltipSortByMetric | boolean | No | false | Whether to sort tooltip by the selected metric in descending order |
| tooltipTimeFormat | string | No | 'smart_date' | Time format for tooltip timestamps |
| y_axis_format | string | No | 'SMART_NUMBER' | Number format for y-axis (e.g., 'SMART_NUMBER', '.2f', '$,.2f') |
| currency_format | object | No | null | Currency format configuration object |
| logAxis | boolean | No | false | Use logarithmic scale for y-axis |
| minorSplitLine | boolean | No | false | Draw split lines for minor y-axis ticks |
| truncateXAxis | boolean | No | true | Truncate x-axis. Can be overridden by specifying bounds. Only for numerical x-axis |
| xAxisBounds | array | No | [null, null] | Min and max bounds for numerical x-axis [min, max] |
| truncateYAxis | boolean | No | false | Truncate y-axis. Can be overridden by specifying bounds |
| y_axis_bounds | array | No | [null, null] | Min and max bounds for y-axis [min, max] |
| annotation_layers | array | No | [] | List of annotation layer objects to display on the chart |
| forecastEnabled | boolean | No | false | Enable time series forecasting |
| forecastPeriods | integer | No | 10 | Number of periods to forecast into the future |
| forecastInterval | number | No | 0.8 | Confidence interval for forecast (0-1) |
| forecastSeasonalityDaily | boolean | No | null | Apply daily seasonality to forecast |
| forecastSeasonalityWeekly | boolean | No | null | Apply weekly seasonality to forecast |
| forecastSeasonalityYearly | boolean | No | null | Apply yearly seasonality to forecast |

### Example Request
```json
{
  "slice_name": "Monthly Revenue by Product Category",
  "viz_type": "echarts_area",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"x_axis\":\"order_date\",\"time_grain_sqla\":\"P1M\",\"metrics\":[\"revenue\"],\"groupby\":[\"product_category\"],\"row_limit\":10000,\"opacity\":0.6,\"stack\":\"Stack\",\"show_legend\":true,\"legendType\":\"scroll\",\"legendOrientation\":\"top\",\"seriesType\":\"smooth\",\"y_axis_format\":\"$,.0f\",\"rich_tooltip\":true,\"showTooltipTotal\":true,\"markerEnabled\":false,\"zoomable\":true,\"adhoc_filters\":[],\"annotation_layers\":[],\"color_scheme\":\"supersetColors\",\"truncateYAxis\":false,\"y_axis_bounds\":[null,null],\"sort_series_type\":\"sum\",\"sort_series_ascending\":false,\"show_value\":false,\"only_total\":true}",
  "description": "Monthly revenue breakdown by product category showing cumulative sales trends",
  "owners": [1],
  "dashboards": [5]
}
```

## Response Format

The chart creation endpoint returns a response containing the created chart's details:

```json
{
  "id": 123,
  "slice_name": "Monthly Revenue by Product Category",
  "viz_type": "echarts_area",
  "datasource_id": 1,
  "datasource_type": "table",
  "description": "Monthly revenue breakdown by product category showing cumulative sales trends",
  "cache_timeout": null,
  "owners": [1],
  "dashboards": [5]
}
```

## Notes

- **Time Series Data**: Area charts are designed for time-series data. Ensure your x_axis field references a temporal column
- **Stacking Options**: The area chart supports four stacking modes:
  - `null`: No stacking, overlapping areas
  - `"Stack"`: Stack areas on top of each other
  - `"Stream"`: Centered stream graph
  - `"Expand"`: Stack to 100%, showing proportions
- **Series Limit**: Use `limit` with `timeseries_limit_metric` to control the number of series when dealing with high-cardinality groupby columns
- **Forecasting**: Enable `forecastEnabled` to add Prophet-based forecasting to your time series
- **Annotations**: Supports Event, Formula, Interval, and Time Series annotation types
- **Performance**: For large datasets, adjust `row_limit` and consider using time grain aggregation via `time_grain_sqla`
- **Opacity**: Lower opacity values (0.2-0.4) work well for overlapping areas, while higher values (0.6-0.8) are better for stacked charts
