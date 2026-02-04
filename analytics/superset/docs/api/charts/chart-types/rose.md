# Rose Chart (`rose`)

## Description
The Nightingale Rose Chart (also known as a polar area chart or coxcomb chart) is a polar coordinate visualization where the circle is broken into wedges of equal angle. Each wedge's value is represented by its area rather than its radius or sweep angle. This chart is particularly effective for displaying cyclical data or comparing multiple time series across different categories over time. Named after Florence Nightingale who used this visualization to illustrate mortality causes during the Crimean War, it combines the strengths of pie charts and bar charts while adding a temporal or categorical dimension.

## When to Use
Use this chart when you need to visualize time series data across multiple categories in a circular format that emphasizes cyclical patterns. It's particularly effective when the time dimension has natural periodicity (hourly, daily, weekly, monthly) and you want to compare multiple metrics or categories simultaneously. The rose chart excels at showing both magnitude and temporal patterns, making it ideal for data that repeats over time cycles.

## Example Use Cases
- Analyzing hourly website traffic patterns across different days of the week
- Comparing monthly sales performance across multiple product categories over a year
- Visualizing energy consumption patterns throughout the day across different building zones
- Tracking customer support ticket volumes by hour across different priority levels
- Displaying seasonal revenue patterns across different business units
- Monitoring temperature or weather patterns across months for multiple locations

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `rose` |
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
The `params` field must be a JSON-encoded string containing an object with the following fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| granularity | string | No | 'one day' | The time granularity for the visualization. Supports natural language (e.g., '10 seconds', '1 day', '56 weeks') or ISO 8601 duration format. |
| granularity_sqla | string | No | null | Name of the time column in the datasource. Used for legacy time filtering. |
| time_grain_sqla | string | No | 'P1D' | Time grain for grouping temporal data. Controls the temporal resolution of the chart (e.g., 'P1D' for daily, 'P1W' for weekly, 'P1M' for monthly). |
| time_range | string | No | 'Last week' | Time range for filtering data. Accepts relative ranges (e.g., 'Last month', 'Last year') or absolute ranges (e.g., '2023-01-01 : 2023-12-31'). |
| metrics | array | Yes | [] | List of metrics to visualize. Each metric can be a string (saved metric name) or an adhoc metric object with aggregation details. |
| adhoc_filters | array | No | [] | Filters to apply to the data. Each filter is an object with properties like clause, subject, operator, comparator, and expressionType. |
| groupby | array | No | [] | Columns to group by. These create the different colored segments/series in the rose chart. |
| limit | integer | No | null | Row limit for the query. Limits the number of rows returned from the datasource. |
| timeseries_limit_metric | object/string | No | null | Metric used for limiting time series. When specified, limits series based on this metric's values. |
| order_desc | boolean | No | true | Whether to sort results in descending order by the metric. |
| contribution | boolean | No | false | Compute the contribution to the total. When enabled, values are shown as percentages of the total. |
| row_limit | integer | No | 10000 | Maximum number of rows to retrieve from the datasource. Acts as a safety limit for query performance. |
| color_scheme | string | No | 'supersetColors' | Color scheme for rendering the chart. Must be a valid color scheme name from the available categorical schemes. |
| number_format | string | No | 'SMART_NUMBER' | D3 format string for numeric values. Controls how numbers are displayed in tooltips and labels. |
| date_time_format | string | No | 'smart_date' | Format string for date/time values. Controls how temporal data is displayed in tooltips and labels. |
| rich_tooltip | boolean | No | true | Whether to show a rich tooltip with all series for that point in time. When enabled, hovering shows all values at that time point. |
| rose_area_proportion | boolean | No | false | Use segment area instead of segment radius for proportioning. When true, the area of each wedge is proportional to the value; when false, the radius is proportional. |
| rolling_type | string | No | 'None' | Rolling window function to apply ('None', 'mean', 'sum', 'std', 'cumsum'). Applies aggregation over a sliding time window. |
| rolling_periods | integer | No | null | Size of the rolling window function in number of periods, relative to the time granularity selected. |
| min_periods | integer | No | null | Minimum number of rolling periods required to show a value. Helps hide "ramp up" data at the beginning of the time series. |
| time_compare | array | No | [] | Time shifts to overlay for comparison. Each value is a relative time delta in natural language (e.g., '1 day', '1 week', '1 year'). Overlays historical data for comparison. |
| comparison_type | string | No | 'values' | How to display time shifts. Options: 'values' (actual values), 'absolute' (difference), 'percentage' (percentage change), 'ratio' (ratio between series). |
| resample_rule | string | No | null | Pandas resample rule for resampling time series data (e.g., '1T', '1H', '1D', '7D', '1M', '1AS'). |
| resample_method | string | No | null | Pandas resample fill method for handling missing values after resampling. Options: 'asfreq', 'bfill', 'ffill', 'median', 'mean', 'sum'. |

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

For temporal filters:
```json
{
  "clause": "WHERE",
  "subject": "date_column",
  "operator": "TEMPORAL_RANGE",
  "comparator": "Last month",
  "expressionType": "SIMPLE"
}
```

### Example Request
```json
{
  "slice_name": "Hourly Sales by Product Category",
  "viz_type": "rose",
  "datasource_id": 15,
  "datasource_type": "table",
  "params": "{\"granularity_sqla\": \"order_timestamp\", \"time_grain_sqla\": \"PT1H\", \"time_range\": \"Last month\", \"metrics\": [{\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"sales_amount\", \"type\": \"DOUBLE\"}, \"aggregate\": \"SUM\", \"label\": \"Total Sales\"}], \"groupby\": [\"product_category\"], \"adhoc_filters\": [], \"limit\": 50, \"order_desc\": true, \"contribution\": false, \"row_limit\": 10000, \"color_scheme\": \"supersetColors\", \"number_format\": \"$,.2f\", \"date_time_format\": \"%-I %p\", \"rich_tooltip\": true, \"rose_area_proportion\": false, \"rolling_type\": \"None\"}",
  "description": "Rose chart showing hourly sales patterns across different product categories for the last month",
  "owners": [1],
  "dashboards": [3]
}
```

## Parameter Details

### Time Granularity Options
The `time_grain_sqla` field accepts ISO 8601 duration values:
- `PT5S` - 5 seconds
- `PT30S` - 30 seconds
- `PT1M` - 1 minute
- `PT5M` - 5 minutes
- `PT30M` - 30 minutes
- `PT1H` - 1 hour
- `PT6H` - 6 hours
- `P1D` - 1 day (default)
- `P7D` - 7 days
- `P1W` - week
- `P1M` - month
- `P3M` - quarter
- `P1Y` - year

### Number Format Patterns
The `number_format` field accepts D3 format strings:
- `SMART_NUMBER` - Automatically formats numbers with appropriate SI prefixes (default)
- `,d` - Comma-separated integers (e.g., 1,234)
- `.2f` - Fixed decimal with 2 places (e.g., 123.45)
- `.3s` - SI-prefix with 3 significant digits (e.g., 1.23k)
- `.2%` - Percentage with 2 decimal places (e.g., 12.34%)
- `$,.2f` - Currency format (e.g., $1,234.56)

### Date Time Format Options
The `date_time_format` field supports various formats:
- `smart_date` - Automatically selects appropriate format based on granularity (default)
- `%Y-%m-%d` - ISO date format (e.g., 2023-12-31)
- `%m/%d/%Y` - US date format (e.g., 12/31/2023)
- `%B %d, %Y` - Long format (e.g., December 31, 2023)
- `%-I:%M %p` - 12-hour time (e.g., 3:45 PM)
- `%H:%M` - 24-hour time (e.g., 15:45)

### Rolling Window Functions
When using advanced analytics with rolling windows:
- `rolling_type`: Choose aggregation function
  - `None` - No rolling window (default)
  - `mean` - Moving average
  - `sum` - Cumulative or moving sum
  - `std` - Standard deviation over window
  - `cumsum` - Cumulative sum
- `rolling_periods`: Number of time periods to include in the window
- `min_periods`: Minimum periods required before showing values (helps hide "ramp up" data)

### Time Comparison
The `time_compare` array enables temporal comparisons:
- Accepts relative time deltas: `['1 day', '1 week', '1 month', '1 year']`
- Common presets: '1 day', '1 week', '28 days', '30 days', '52 weeks', '1 year', '2 years', '3 years'
- Free text is supported for custom periods
- Works with `comparison_type` to control display:
  - `values` - Show actual values from different time periods
  - `absolute` - Show difference from main series
  - `percentage` - Show percentage change
  - `ratio` - Show ratio between series and time shifts

### Resampling
For time series data manipulation:
- `resample_rule`: Time frequency to resample to using Pandas frequency strings
  - `1T` - 1 minute
  - `1H` - 1 hour
  - `1D` - 1 day
  - `7D` - 7 days
  - `1M` - 1 month (end of month)
  - `1AS` - 1 year (start of year)
- `resample_method`: How to fill or aggregate values after resampling
  - `asfreq` - Return values at the new frequency without filling
  - `bfill` - Backward fill (use next valid value)
  - `ffill` - Forward fill (use previous valid value)
  - `median` - Use median of values in each period
  - `mean` - Use mean of values in each period
  - `sum` - Sum values in each period

### Rose Area Proportion
The `rose_area_proportion` parameter controls how values are represented:
- `false` (default): Segment radius is proportional to the value. This creates a more dramatic visual difference between values but can be harder to compare precisely.
- `true`: Segment area is proportional to the value. This provides more accurate visual comparison but less dramatic differences between values.

Choose area proportion when precise visual comparison is important; choose radius proportion when you want to emphasize differences and dramatic visual impact.

## Notes
- This chart type is marked as **Legacy** and uses the legacy API (`useLegacyApi: true`)
- The rose chart is most effective with cyclical time data (hours of day, days of week, months of year)
- When using `groupby`, each group creates a separate colored series/wedge at each time point
- The chart works best with 5-20 time points; too many time points can make the chart cluttered
- Consider using `contribution: true` to show relative proportions rather than absolute values
- The `rich_tooltip` option is highly recommended for comparing multiple series at each time point
- Advanced analytics features (rolling windows, time comparison, resampling) are available through the Advanced Analytics section
- Color schemes should be categorical rather than sequential for best results with multiple series
