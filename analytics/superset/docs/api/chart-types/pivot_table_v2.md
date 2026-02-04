# Pivot Table (`pivot_table_v2`)

## Description
The Pivot Table is a tabular visualization that summarizes data by grouping multiple statistics along two axes (rows and columns). It displays aggregated metrics in a grid format where each cell represents the intersection of row and column groupings. The table supports features like subtotals, totals, conditional formatting, and various sorting options, making it ideal for detailed data analysis and reporting.

## When to Use
Use the Pivot Table when you need to compare metrics across multiple dimensions simultaneously, analyze data at various levels of granularity with subtotals, or create comprehensive reports that show relationships between categorical variables. This visualization is particularly valuable when working with multi-dimensional data that requires both row and column hierarchies.

## Example Use Cases
- Sales analysis by region and product category with monthly breakdown
- Employee performance metrics grouped by department and role
- Budget tracking across cost centers and expense types over time
- Customer segmentation showing purchase behavior by age group and location
- Inventory management displaying stock levels by warehouse and product line

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `pivot_table_v2` |
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

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| groupbyColumns | array | No | [] | Columns to group by on the columns axis. Array of column names (strings) or adhoc column objects. |
| groupbyRows | array | No | [] | Columns to group by on the rows axis. Array of column names (strings) or adhoc column objects. |
| time_grain_sqla | string | No | null | Time granularity for temporal columns (e.g., 'PT1H', 'P1D', 'P1W', 'P1M'). Only visible when temporal columns are selected in groupbyColumns or groupbyRows. |
| temporal_columns_lookup | object | No | null | Lookup object mapping column names to their temporal properties. Used internally to determine which columns should respect time grain settings. |
| metrics | array | Yes | - | Array of metrics to display. Can be metric names (strings) or adhoc metric objects. At least one metric is required. |
| metricsLayout | string | No | 'COLUMNS' | Apply metrics on rows or columns. Valid values: 'COLUMNS' (metrics appear as separate columns), 'ROWS' (metrics appear as separate rows). |
| adhoc_filters | array | No | [] | Array of adhoc filter objects to filter the data before aggregation. |
| series_limit | integer | No | null | Limits the number of series that get displayed. Applied before row_limit. |
| row_limit | integer | No | 10000 | Limits the number of cells that get retrieved from the database. |
| series_limit_metric | object/string | No | null | Metric used to define how the top series are sorted if a series or cell limit is present. If undefined, reverts to the first metric. |
| order_desc | boolean | No | true | Whether to sort descending (true) or ascending (false) when applying series or row limits. |
| aggregateFunction | string | No | 'Sum' | Aggregate function to apply when pivoting and computing the total rows and columns. Options: 'Count', 'Count Unique Values', 'List Unique Values', 'Sum', 'Average', 'Median', 'Sample Variance', 'Sample Standard Deviation', 'Minimum', 'Maximum', 'First', 'Last', 'Sum as Fraction of Total', 'Sum as Fraction of Rows', 'Sum as Fraction of Columns', 'Count as Fraction of Total', 'Count as Fraction of Rows', 'Count as Fraction of Columns'. |
| rowTotals | boolean | No | false | Display row level total. Shows aggregated values for each row across all columns. |
| rowSubTotals | boolean | No | false | Display row level subtotal. Shows intermediate aggregations for hierarchical row groupings. |
| colTotals | boolean | No | false | Display column level total. Shows aggregated values for each column across all rows. |
| colSubTotals | boolean | No | false | Display column level subtotal. Shows intermediate aggregations for hierarchical column groupings. |
| transposePivot | boolean | No | false | Swap rows and columns. Exchanges the groupbyRows and groupbyColumns axes. |
| combineMetric | boolean | No | false | Display metrics side by side within each column, as opposed to each column being displayed side by side for each metric. Affects how multiple metrics are laid out in the table. |
| valueFormat | string | No | 'SMART_NUMBER' | Number format for metric values. Uses D3 format strings (e.g., '.2f' for 2 decimal places, ',d' for comma-separated integers, '.1%' for percentages). |
| currency_format | object | No | null | Currency format configuration object with properties for symbol, symbolPosition, and other currency display settings. Applied to metrics when currency formatting is needed. |
| date_format | string | No | 'smart_date' | D3 time format for datetime columns (e.g., '%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%B %d, %Y'). Special value 'smart_date' applies intelligent formatting based on the time range. |
| rowOrder | string | No | 'key_a_to_z' | Sort rows by key or value. Options: 'key_a_to_z' (sort row names A-Z), 'key_z_to_a' (sort row names Z-A), 'value_a_to_z' (sort by metric values ascending), 'value_z_to_a' (sort by metric values descending). |
| colOrder | string | No | 'key_a_to_z' | Sort columns by key or value. Options: 'key_a_to_z' (sort column names A-Z), 'key_z_to_a' (sort column names Z-A), 'value_a_to_z' (sort by metric values ascending), 'value_z_to_a' (sort by metric values descending). |
| rowSubtotalPosition | boolean | No | false | Position of row level subtotal. true = Top (subtotals appear above their group), false = Bottom (subtotals appear below their group). |
| colSubtotalPosition | boolean | No | false | Position of column level subtotal. true = Left (subtotals appear before their group), false = Right (subtotals appear after their group). |
| conditional_formatting | array | No | [] | Array of conditional formatting rule objects to apply color formatting to metrics based on their values. Each rule specifies a column, operator, target value, and color scheme. |
| allow_render_html | boolean | No | true | Renders table cells as HTML when applicable. For example, HTML &lt;a&gt; tags will be rendered as hyperlinks. Set to false to display raw HTML strings. |

### Example Request
```json
{
  "slice_name": "Quarterly Sales by Region and Product",
  "viz_type": "pivot_table_v2",
  "datasource_id": 123,
  "datasource_type": "table",
  "params": "{\"groupbyColumns\": [\"region\"], \"groupbyRows\": [\"product_category\", \"product_name\"], \"metrics\": [\"sum__sales\", \"avg__price\"], \"metricsLayout\": \"COLUMNS\", \"aggregateFunction\": \"Sum\", \"rowTotals\": true, \"colTotals\": true, \"rowSubTotals\": true, \"colSubTotals\": false, \"valueFormat\": \"$,.2f\", \"date_format\": \"smart_date\", \"rowOrder\": \"value_z_to_a\", \"colOrder\": \"key_a_to_z\", \"row_limit\": 10000, \"order_desc\": true, \"transposePivot\": false, \"combineMetric\": false, \"rowSubtotalPosition\": false, \"colSubtotalPosition\": false, \"allow_render_html\": true, \"adhoc_filters\": [{\"clause\": \"WHERE\", \"comparator\": \"2023\", \"expressionType\": \"SIMPLE\", \"operator\": \"TEMPORAL_RANGE\", \"subject\": \"order_date\"}], \"conditional_formatting\": [{\"column\": \"sum__sales\", \"operator\": \">\", \"targetValue\": 100000, \"colorScheme\": \"#00FF00\"}]}",
  "description": "Sales performance analysis showing revenue and average price by region and product",
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

### Aggregate Functions
The `aggregateFunction` determines how values are combined when computing totals and subtotals:

**Basic Aggregations:**
- `Count` - Count of all values
- `Count Unique Values` - Count of distinct values
- `List Unique Values` - Comma-separated list of unique values
- `Sum` - Sum of all values
- `Average` - Mean of all values
- `Median` - Middle value when sorted
- `Sample Variance` - Variance with N-1 denominator
- `Sample Standard Deviation` - Standard deviation with N-1 denominator
- `Minimum` - Smallest value
- `Maximum` - Largest value
- `First` - First value encountered
- `Last` - Last value encountered

**Fractional Aggregations:**
- `Sum as Fraction of Total` - Each cell as fraction of grand total
- `Sum as Fraction of Rows` - Each cell as fraction of row total
- `Sum as Fraction of Columns` - Each cell as fraction of column total
- `Count as Fraction of Total` - Count as fraction of grand total
- `Count as Fraction of Rows` - Count as fraction of row total
- `Count as Fraction of Columns` - Count as fraction of column total

### Number Format Patterns
The `valueFormat` field accepts D3 format strings:
- `,d` - Comma-separated integers (e.g., 1,234)
- `.2f` - Fixed decimal with 2 places (e.g., 123.45)
- `.3s` - SI-prefix with 3 significant digits (e.g., 1.23k)
- `.2%` - Percentage with 2 decimal places (e.g., 12.34%)
- `$,.2f` - Currency format (e.g., $1,234.56)
- `SMART_NUMBER` - Automatic intelligent formatting

### Date Format Patterns
The `date_format` field accepts D3 time format strings:
- `smart_date` - Intelligent formatting based on time range (default)
- `%Y-%m-%d` - Year-month-day (e.g., 2023-01-15)
- `%Y-%m-%d %H:%M:%S` - Full timestamp (e.g., 2023-01-15 14:30:00)
- `%B %d, %Y` - Month name, day, year (e.g., January 15, 2023)
- `%m/%d/%Y` - US format (e.g., 01/15/2023)
- `%d/%m/%Y` - European format (e.g., 15/01/2023)

### Conditional Formatting
The `conditional_formatting` array contains objects with the following structure:
```json
{
  "column": "metric_name",
  "operator": ">",
  "targetValue": 1000,
  "colorScheme": "#00FF00"
}
```

Supported operators: `>`, `<`, `>=`, `<=`, `==`, `!=`, `between`, `not between`

## Chart Behaviors
This chart supports the following interactive behaviors:
- **InteractiveChart** - Supports cross-filtering and drill-down interactions
- **DrillToDetail** - Allows drilling into underlying data records
- **DrillBy** - Supports drilling by additional dimensions

## Notes
- The `metrics` field is required and must contain at least one metric.
- Time grain controls are only visible when temporal columns are selected in `groupbyColumns` or `groupbyRows`.
- The `metricsLayout` field determines whether metrics appear as separate columns or separate rows in the pivot table.
- When using `conditional_formatting`, ensure the specified columns match the metrics defined in the `metrics` array.
- The `aggregateFunction` is used for computing totals and subtotals, not for the main metric calculations which are defined in the metrics themselves.
- Large pivot tables with many dimensions may require increasing the `row_limit` value to avoid truncation.
- The table supports both physical columns (referenced by name) and adhoc columns (custom SQL expressions) in grouping fields.
- When both `series_limit` and `row_limit` are specified, `series_limit` is applied first at the query level, then `row_limit` caps the final result set.
- The `order_desc` parameter works in conjunction with `series_limit_metric` to determine sort direction when limiting results.
- Subtotals and totals respect the `aggregateFunction` setting and can be positioned using `rowSubtotalPosition` and `colSubtotalPosition`.
- The `combineMetric` option is particularly useful when comparing multiple metrics side-by-side within dimensional groups rather than having metrics as separate top-level groups.
