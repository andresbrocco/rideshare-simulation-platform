# Partition Chart (`partition`)

## Description
The Partition Chart visualizes hierarchical data using a space-filling layout where the area of each partition represents the value of a metric. It compares the same summarized metric across multiple groups, showing both the hierarchical relationships and the relative magnitudes of values through partition sizes. The chart supports time series analysis with multiple aggregation options and advanced analytics capabilities.

## When to Use
Use this chart type when you need to display hierarchical categorical data with proportional representation of values. It is particularly effective for showing part-to-whole relationships across multiple dimensions and understanding how values are distributed across categories, especially when comparing time series data or performing temporal analysis.

## Example Use Cases
- Analyzing sales distribution across regions, countries, and cities with revenue shown proportionally
- Visualizing website traffic by traffic source, campaign, and landing page with visitor counts
- Comparing product category performance by department, category, and subcategory with sales metrics
- Examining budget allocation across divisions, departments, and cost centers
- Tracking inventory levels across warehouses, zones, and product categories

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `partition` |
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
The `params` field must be a JSON-encoded string containing the following chart-specific parameters:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| metrics | array | Yes | [] | One or more metrics to display. Can be strings (saved metric names) or adhoc metric objects. |
| groupby | array | Yes | [] | Columns to group by for hierarchical display. Order determines hierarchy levels. |
| adhoc_filters | array | No | [] | List of adhoc filters to apply to the data. Each filter is an object with properties like clause, subject, operator, comparator, and expressionType. |
| time_series_option | string | No | 'not_time' | Time series handling mode. Valid options: 'not_time' (ignore time), 'time_series' (standard time series), 'agg_mean' (mean over period), 'agg_sum' (sum over period), 'point_diff' (difference from since to until), 'point_percent' (percent change from since to until), 'point_factor' (factor change from since to until), 'adv_anal' (use advanced analytics). |
| contribution | boolean | No | false | When true, computes the contribution to the total for each partition. |
| limit | integer | No | null | Series limit. Limits the number of series displayed using a subquery. Useful when grouping by high cardinality columns. |
| timeseries_limit_metric | object/string | No | null | Metric used to order and limit the number of series when limit is specified. Can be a string (saved metric) or adhoc metric object. |
| order_desc | boolean | No | true | When true, sorts results in descending order. When false, sorts ascending. Only visible/applicable when timeseries_limit_metric is set. |
| row_limit | integer | No | 10000 | Maximum number of rows computed in the query (0-max configured limit). |
| color_scheme | string | No | 'supersetColors' | Color scheme for rendering the chart. Must be a valid color scheme name from the available schemes. |
| number_format | string | No | 'SMART_NUMBER' | D3 format string for numeric values. Supports standard D3 formatting options. |
| date_time_format | string | No | 'smart_date' | D3 format string for date/time values. Supports standard D3 time formatting options. |
| partition_limit | integer | No | 5 | Maximum number of subdivisions of each group. Lower values are pruned first. |
| partition_threshold | number | No | 0.05 | Partitions whose height to parent height proportions are below this value are pruned. Accepts decimal values (e.g., 0.05 = 5%). |
| log_scale | boolean | No | false | When true, uses logarithmic scale for partition sizing. |
| equal_date_size | boolean | No | true | When true, forces date partitions to have the same height regardless of their value. |
| rich_tooltip | boolean | No | true | When true, displays a rich tooltip showing a list of all series for that point in time. |
| rolling_type | string | No | 'None' | Rolling window function to apply. Valid options: 'None', 'mean', 'sum', 'std', 'cumsum'. Works with rolling_periods. |
| rolling_periods | integer | No | null | Size of the rolling window function relative to the time granularity selected. |
| min_periods | integer | No | null | Minimum number of rolling periods required to show a value. Hides the "ramp up" period. |
| time_compare | array | No | [] | List of time shifts for comparison (e.g., ['1 day', '1 week', '1 year']). Supports natural language or exact durations. |
| comparison_type | string | No | 'values' | How to display time shifts. Valid options: 'values' (actual values), 'absolute' (difference), 'percentage' (percentage change), 'ratio' (ratio between series and time shifts). |
| resample_rule | string | No | null | Pandas resample rule for resampling time series data. Valid options: '1T', '1H', '1D', '7D', '1M', '1AS', or custom. |
| resample_method | string | No | null | Pandas resample method. Valid options: 'asfreq', 'bfill', 'ffill', 'median', 'mean', 'sum'. |

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
    "column_name": "sales_amount",
    "type": "DOUBLE"
  },
  "aggregate": "SUM",
  "label": "Total Sales"
}
```

Or for SQL expression:
```json
{
  "expressionType": "SQL",
  "sqlExpression": "SUM(price * quantity)",
  "label": "Revenue"
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

### Example Request
```json
{
  "slice_name": "Sales Distribution by Region and Category",
  "viz_type": "partition",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"metrics\": [{\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"sales_amount\", \"type\": \"DOUBLE\"}, \"aggregate\": \"SUM\", \"label\": \"Total Sales\"}], \"groupby\": [\"region\", \"product_category\"], \"adhoc_filters\": [{\"clause\": \"WHERE\", \"subject\": \"order_date\", \"operator\": \"TEMPORAL_RANGE\", \"comparator\": \"Last quarter\", \"expressionType\": \"SIMPLE\"}], \"time_series_option\": \"not_time\", \"contribution\": false, \"limit\": 50, \"row_limit\": 10000, \"color_scheme\": \"supersetColors\", \"number_format\": \"$,.0f\", \"date_time_format\": \"smart_date\", \"partition_limit\": 5, \"partition_threshold\": 0.05, \"log_scale\": false, \"equal_date_size\": true, \"rich_tooltip\": true}",
  "description": "Partition chart showing sales distribution across regions and product categories",
  "owners": [1]
}
```

### Example with Time Series Analysis
```json
{
  "slice_name": "Monthly Sales Trends with Rolling Average",
  "viz_type": "partition",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"metrics\": [\"SUM(revenue)\"], \"groupby\": [\"department\", \"category\"], \"time_series_option\": \"time_series\", \"contribution\": true, \"row_limit\": 5000, \"color_scheme\": \"d3Category20\", \"number_format\": \"SMART_NUMBER\", \"partition_limit\": 10, \"partition_threshold\": 0.03, \"log_scale\": false, \"equal_date_size\": false, \"rich_tooltip\": true, \"rolling_type\": \"mean\", \"rolling_periods\": 7, \"min_periods\": 3, \"time_compare\": [\"1 year\"], \"comparison_type\": \"percentage\"}",
  "description": "Time series partition chart with rolling averages and year-over-year comparison",
  "owners": [1]
}
```

## Notes
- This chart type is marked as **Legacy** and uses the legacy API
- The `groupby` field order determines the hierarchy - first column is the top level, subsequent columns are nested levels
- The `partition_limit` parameter controls how many subdivisions appear in each group, pruning smaller values first
- The `partition_threshold` determines the minimum proportional size for a partition to be displayed (as a fraction of parent height)
- When `contribution` is enabled, values are shown as percentages of the total rather than absolute values
- Time series options provide various ways to aggregate or compare temporal data
- Advanced analytics features include rolling windows, time comparisons, and resampling for sophisticated temporal analysis
- The `equal_date_size` option is useful for time-based partitions to ensure consistent visual spacing regardless of metric values
- Rich tooltips provide detailed information about all series at a given point, enhancing data exploration
- Log scale is useful when partition values span multiple orders of magnitude
- Format strings support D3 formatting syntax for both numeric displays and date/time representations
