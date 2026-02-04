# Time Table (`time_table`)

## Description
The Time-series Table visualizes multiple time series metrics side by side in a tabular format, with each row representing either a metric or a grouped column value. Each column in the table can display different types of comparisons including sparklines (inline charts), time-based comparisons, contribution percentages, or period averages. This visualization is ideal for comparing trends and patterns across multiple metrics simultaneously in a compact, information-dense format.

## When to Use
Use this chart type when you need to compare multiple time series metrics or grouped values in a compact table format, display inline sparkline visualizations alongside numerical values, perform time-based comparisons showing changes over periods, or analyze contribution percentages and period averages across multiple dimensions. This visualization excels at providing a comprehensive overview of multiple metrics with their trends in a single view.

## Example Use Cases
- Dashboard KPI summary showing current values, trends (sparklines), and period-over-period changes for key business metrics
- Sales performance comparison across products with revenue sparklines, week-over-week changes, and contribution percentages
- Server monitoring dashboard displaying current metrics with embedded trend charts and time lag comparisons
- Financial reporting showing multiple metrics with their trends, year-over-year comparisons, and percentage contributions
- Marketing campaign performance with engagement metrics, sparkline trends, and comparison to previous periods

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `time_table` |
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
| metrics | array | Yes | - | Array of metrics to display. Can be metric names (strings) or adhoc metric objects. Each metric becomes a row in the table (unless groupby is specified). At least one metric is required. |
| groupby | array | No | [] | Column to group by. If specified, each unique value in this column becomes a row in the table instead of metrics. Only a single column is supported (not an array of multiple columns). |
| granularity | string | No | null | Name of the time column for legacy Druid datasources. Used for time-based filtering. |
| granularity_sqla | string | No | null | Name of the temporal column for SQL-based datasources. Used to define the time dimension. |
| time_grain_sqla | string | No | null | Time granularity for temporal aggregation (e.g., 'PT1H', 'P1D', 'P1W', 'P1M'). Determines the time buckets for the time series data. |
| time_range | string | No | 'Last week' | Time range for the query. Can be a relative time range like 'Last week', 'Last month', or an explicit range. |
| adhoc_filters | array | No | [] | Array of adhoc filter objects to filter the data before aggregation. Each filter specifies conditions on columns or metrics. |
| limit | integer | No | null | Series limit. Limits the number of series (time points) displayed in the visualization. |
| row_limit | integer | No | 1000 | Maximum number of rows to retrieve from the datasource. Limits the result set size. |
| column_collection | array | Yes | - | Array of column configuration objects defining how each column in the table should be displayed. Each object configures a time series column with its display properties. Required and must contain at least one column configuration. |
| url | string | No | '' | Templated URL that can include dynamic values from the data. Use template variables like `{{ metric }}` or other column values to create dynamic links. |

### column_collection Configuration
The `column_collection` array contains objects defining each column in the time-series table. Each column configuration object supports the following properties:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| key | string | Yes | - | Unique identifier for this column configuration. Used internally to reference the column. |
| label | string | No | '' | Display label for the column header. Shown at the top of the column in the table. |
| tooltip | string | No | '' | Tooltip text that appears when hovering over the column header. Provides additional context about the column. |
| colType | string | No | '' | Type of column visualization. Options: 'time' (time comparison), 'contrib' (contribution percentage), 'spark' (sparkline chart), 'avg' (period average). Determines how the column data is calculated and displayed. |
| sparkType | string | No | 'line' | Type of chart for sparkline columns (only applies when colType is 'spark'). Options: 'line' (line chart), 'bar' (bar chart), 'area' (area chart). |
| width | string | No | '' | Width of the sparkline in pixels (only applies when colType is 'spark'). Examples: '100', '150'. |
| height | string | No | '' | Height of the sparkline in pixels (only applies when colType is 'spark'). Examples: '50', '75'. |
| timeLag | integer | No | 0 | Number of time periods to compare against (applies to 'time' and 'avg' column types). Positive values compare to past periods, negative values can compare from the beginning of the time range. |
| timeRatio | string/number | No | '' | Number of periods to ratio against (applies to 'spark' column type). Used for calculating ratios in sparkline columns. |
| comparisonType | string | No | '' | Type of comparison for time columns (only applies when colType is 'time'). Options: 'value' (actual value), 'diff' (difference), 'perc' (percentage), 'perc_change' (percentage change). |
| showYAxis | boolean | No | false | Whether to show Y-axis on sparklines (only applies when colType is 'spark'). Displays the min/max scale on the sparkline chart. |
| yAxisBounds | array | No | [null, null] | Manually set min/max values for the sparkline Y-axis as [min, max] (only applies when colType is 'spark'). When null, bounds are automatically determined from the data. |
| bounds | array | No | [null, null] | Number bounds used for color encoding from red to blue as [min, max] (applies to non-sparkline columns). Reverse the numbers for blue to red coloring. To get pure red or blue, enter only min or max. |
| d3format | string | No | '' | D3 format string for number formatting. Examples: ',.2f' (comma-separated with 2 decimals), '.1%' (percentage with 1 decimal), '$,.0f' (currency). |
| dateFormat | string | No | '' | D3 date format string for sparkline tooltips (only applies when colType is 'spark'). Examples: '%Y-%m-%d', '%B %d, %Y'. |

### Metric Object Format
Metrics in the `metrics` array can be specified as either:

**Simple string format** (for saved metrics):
```json
"COUNT(*)"
```

**Adhoc metric object** (for custom aggregations):
```json
{
  "expressionType": "SIMPLE",
  "column": {
    "column_name": "revenue",
    "type": "DOUBLE"
  },
  "aggregate": "SUM",
  "label": "Total Revenue"
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
  "slice_name": "Weekly Sales Performance Overview",
  "viz_type": "time_table",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"metrics\": [{\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"sales_amount\", \"type\": \"DOUBLE\"}, \"aggregate\": \"SUM\", \"label\": \"Total Sales\"}, {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"order_count\", \"type\": \"INTEGER\"}, \"aggregate\": \"COUNT\", \"label\": \"Orders\"}], \"groupby\": [], \"granularity_sqla\": \"order_date\", \"time_grain_sqla\": \"P1D\", \"time_range\": \"Last month\", \"adhoc_filters\": [{\"clause\": \"WHERE\", \"subject\": \"status\", \"operator\": \"==\", \"comparator\": \"completed\", \"expressionType\": \"SIMPLE\"}], \"limit\": null, \"row_limit\": 1000, \"column_collection\": [{\"key\": \"current_value\", \"label\": \"Current\", \"tooltip\": \"Current period value\", \"colType\": \"time\", \"comparisonType\": \"value\", \"timeLag\": 0, \"d3format\": \"$,.2f\", \"bounds\": [null, null]}, {\"key\": \"trend\", \"label\": \"Trend\", \"tooltip\": \"7-day trend sparkline\", \"colType\": \"spark\", \"sparkType\": \"line\", \"width\": \"150\", \"height\": \"50\", \"showYAxis\": true, \"yAxisBounds\": [null, null], \"d3format\": \"$,.2f\", \"dateFormat\": \"%b %d\"}, {\"key\": \"wow_change\", \"label\": \"WoW Change\", \"tooltip\": \"Week over week percentage change\", \"colType\": \"time\", \"comparisonType\": \"perc_change\", \"timeLag\": 7, \"d3format\": \"+.1%\", \"bounds\": [-0.1, 0.1]}, {\"key\": \"contribution\", \"label\": \"Contribution\", \"tooltip\": \"Contribution to total\", \"colType\": \"contrib\", \"d3format\": \".1%\", \"bounds\": [null, null]}], \"url\": \"/dashboard/sales-detail?metric={{ metric }}\"}",
  "description": "Time-series table showing sales metrics with trends, comparisons, and contributions",
  "owners": [1]
}
```

## Parameter Details

### Time Granularity Options
The `time_grain_sqla` field accepts the following values:
- `PT5S` - 5 seconds
- `PT30S` - 30 seconds
- `PT1M` - 1 minute
- `PT5M` - 5 minutes
- `PT30M` - 30 minutes
- `PT1H` - 1 hour
- `PT6H` - 6 hours
- `P1D` - 1 day
- `P7D` - 7 days
- `P1W` - week
- `P1M` - month
- `P3M` - quarter
- `P1Y` - year

### Column Types
The `colType` field determines how each column displays and calculates its data:

**time** - Time comparison column
- Shows comparisons between current period and a lagged period
- Requires `timeLag` to specify how many periods to look back
- Use `comparisonType` to control display format:
  - `value` - Shows actual metric value
  - `diff` - Shows difference from comparison period
  - `perc` - Shows percentage relative to comparison period
  - `perc_change` - Shows percentage change from comparison period
- Supports color encoding via `bounds` parameter

**contrib** - Contribution column
- Displays each metric's contribution as a percentage of the total
- Useful for understanding relative importance of metrics
- Supports color encoding via `bounds` parameter

**spark** - Sparkline column
- Embeds a mini time-series chart in the table cell
- Requires `width` and `height` for sparkline dimensions
- Use `sparkType` to choose chart style ('line', 'bar', or 'area')
- Optional `showYAxis` displays scale on the sparkline
- Optional `yAxisBounds` manually sets Y-axis range
- Use `timeRatio` for ratio calculations
- Use `dateFormat` to format dates in tooltips

**avg** - Period average column
- Shows average value over a specified period
- Requires `timeLag` to define the averaging window
- Supports color encoding via `bounds` parameter

### Number Format Patterns
The `d3format` field accepts D3 format strings:
- `,d` - Comma-separated integers (e.g., 1,234)
- `.2f` - Fixed decimal with 2 places (e.g., 123.45)
- `,.2f` - Comma-separated with 2 decimals (e.g., 1,234.56)
- `.1%` - Percentage with 1 decimal place (e.g., 12.3%)
- `+.1%` - Percentage with sign (e.g., +12.3% or -5.2%)
- `$,.2f` - Currency format (e.g., $1,234.56)
- `.3s` - SI-prefix with 3 significant digits (e.g., 1.23k)

### Date Format Patterns
The `dateFormat` field accepts D3 time format strings for sparkline tooltips:
- `%Y-%m-%d` - Year-month-day (e.g., 2023-01-15)
- `%Y-%m-%d %H:%M:%S` - Full timestamp (e.g., 2023-01-15 14:30:00)
- `%B %d, %Y` - Month name, day, year (e.g., January 15, 2023)
- `%b %d` - Abbreviated month and day (e.g., Jan 15)
- `%m/%d/%Y` - US format (e.g., 01/15/2023)
- `%d/%m/%Y` - European format (e.g., 15/01/2023)

### URL Templating
The `url` field supports template variables that are replaced with actual values from the data:
- `{{ metric }}` - Replaced with the metric name or label
- Other column values can also be referenced using the same syntax
- Example: `/dashboard/detail?metric={{ metric }}&date={{ date }}`
- The URL becomes clickable, allowing drill-through to detail views

## Chart Behaviors
This chart supports the following behaviors:
- **Legacy Chart** - Uses the legacy API for data fetching
- **Tabular Format** - Displays data in a structured table layout
- **Inline Visualizations** - Embeds sparkline charts within table cells
- **Time Comparisons** - Supports period-over-period analysis
- **Dynamic URLs** - Enables drill-through with templated links

## Notes
- This chart type is marked as **Legacy** and uses the legacy API (useLegacyApi: true)
- The `column_collection` field is required and must contain at least one column configuration
- When `groupby` is specified, rows represent grouped column values; otherwise, rows represent metrics
- The `groupby` field only supports a single column (not multiple columns)
- Time lag comparisons work by offsetting the time series by the specified number of periods
- Sparkline columns provide an inline visualization of the full time series trend
- Color encoding with `bounds` creates a gradient from red (low) to blue (high) unless reversed
- The contribution column type automatically calculates percentages relative to the total
- Each row can have different formatting via the `d3format` setting in column configurations
- The `url` parameter enables creating interactive tables with drill-through capabilities
- Multiple column types can be combined to create comprehensive metric overviews
- Period averages (`avg` column type) calculate the mean over the specified time lag window
- Sparklines respect the `time_grain_sqla` setting for determining time bucket granularity
- When `showYAxis` is enabled on sparklines, the axis displays either manual bounds (if set) or data-driven bounds
- The chart automatically handles both metric-based rows (when groupby is empty) and dimension-based rows (when groupby is specified)
- Tags include: Multi-Variables, Comparison, Legacy, Percentages, Tabular, Text, Trend
