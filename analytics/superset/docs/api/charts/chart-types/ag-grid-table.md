# AG Grid Table (`ag-grid-table`)

## Description
The AG Grid Table chart displays data in a modern, high-performance spreadsheet format powered by AG Grid. This visualization provides an advanced tabular view with enterprise-grade features including sorting, pagination, search functionality, conditional formatting, column customization, and visual enhancements like cell bars. The AG Grid Table (also known as Table V2) supports both raw data records and aggregated metrics, making it suitable for detailed data exploration, reporting, and interactive data analysis.

## When to Use
Use this chart when you need a modern, feature-rich table with advanced capabilities beyond the standard table chart. The AG Grid Table excels at handling large datasets with smooth scrolling, flexible column management, and powerful filtering options. It's ideal when precise values matter more than visual patterns, or when you need to present multiple metrics and dimensions together with enhanced user interactions. The chart supports both aggregate queries (with GROUP BY) and raw data queries, offering flexibility for different analytical needs.

## Example Use Cases
- Building high-performance dashboards with large datasets requiring smooth scrolling and pagination
- Creating executive summary reports with aggregated metrics grouped by region or time period
- Displaying detailed sales records with customer information, order amounts, and dates with advanced filtering
- Building searchable product catalogs with multiple attributes and custom column configurations
- Presenting comparison tables with time-over-time metrics showing absolute and percentage changes
- Creating interactive data browsers with server-side pagination for millions of records
- Displaying financial statements with conditional formatting and cell bars to highlight trends
- Building data exploration tools with column reordering and customizable views

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `ag-grid-table` |
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
| query_mode | string | No | 'aggregate' | Query mode: 'aggregate' (with GROUP BY) or 'raw' (individual records) |
| groupby | array | No | [] | Columns to group by (only in aggregate mode). At least one of groupby, metrics, or percent_metrics required in aggregate mode |
| metrics | array | No | [] | Metrics to display (only in aggregate mode). Can include saved metrics or ad-hoc metrics |
| all_columns | array | No | [] | Columns to display (only in raw mode). Required in raw mode |
| percent_metrics | array | No | [] | Metrics to display as percentages of total (only in aggregate mode) |
| adhoc_filters | array | No | [] | Filters to apply to the data |
| time_grain_sqla | string | No | null | Time granularity when grouping by temporal columns (e.g., 'P1D', 'P1W', 'P1M'). Only visible when grouping by datetime columns |
| temporal_columns_lookup | object | No | {} | Mapping of columns to their temporal granularities for fine-grained control |
| timeseries_limit_metric | string/object | No | null | Metric to use for ordering results (aggregate mode only) |
| order_by_cols | array | No | [] | Columns to order results by in format [[column_name, ascending]] (raw mode only) |
| order_desc | boolean | No | true | Sort in descending order when timeseries_limit_metric is set (aggregate mode only) |
| row_limit | integer | No | 1000 | Maximum number of rows to return. Options: 10, 50, 100, 250, 500, 1000, 5000, 10000, 50000, 100000, 150000, 200000, 250000, 300000, 350000, 400000, 450000, 500000 |
| server_pagination | boolean | No | false | Enable server-side pagination for large datasets (experimental feature) |
| server_page_length | integer | No | 10 | Number of rows per page for server pagination. Options: 10, 20, 50, 100, 200 |
| show_totals | boolean | No | false | Show summary row with aggregated totals (aggregate mode only, not applied to row limit) |
| table_timestamp_format | string | No | 'smart_date' | D3 time format for datetime columns |
| page_length | integer/string | No | null | Client-side rows per page (0 or null means no pagination). Options: 10, 20, 50, 100, 200 |
| include_search | boolean | No | false | Include client-side search box |
| allow_rearrange_columns | boolean | No | false | Allow users to drag-and-drop column headers to reorder columns |
| column_config | object | No | {} | Per-column customization settings (see Column Config section) |
| show_cell_bars | boolean | No | true | Display background bar charts in numeric table columns |
| align_pn | boolean | No | false | Align background charts with both positive and negative values at 0 |
| color_pn | boolean | No | true | Colorize numeric values by whether they are positive or negative |
| conditional_formatting | array | No | [] | Custom conditional formatting rules (see Conditional Formatting section) |
| comparison_color_enabled | boolean | No | false | Enable basic conditional formatting for time comparison columns with arrows (↑ and ↓) |
| comparison_color_scheme | string | No | 'Green' | Color scheme for comparison: 'Green' (increase=green, decrease=red) or 'Red' (increase=red, decrease=green) |
| time_compare | array | No | [] | Time period to compare against (e.g., ['1 week ago'], ['1 month ago']). Only in aggregate mode |

### Column Config Object
The `column_config` field allows per-column customization with keys being column names and values being objects with these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| d3NumberFormat | string | - | D3 number format string for numeric columns (e.g., ',.2f', '.2%', '$,.0f') |
| d3SmallNumberFormat | string | - | Format for small numbers, particularly useful for percentages |
| d3TimeFormat | string | - | D3 time format string for datetime columns (e.g., '%Y-%m-%d', '%B %d, %Y') |
| columnWidth | number | - | Column width in pixels |
| horizontalAlign | string | 'left' | Horizontal alignment: 'left', 'right', or 'center' |
| showCellBars | boolean | true | Show cell bars for this specific column |
| alignPositiveNegative | boolean | false | Align cell bars at zero for this column (useful for columns with positive and negative values) |
| colorPositiveNegative | boolean | true | Color code positive values in one color and negative values in another for this column |
| truncateLongCells | boolean | false | Truncate long cell content with ellipsis |
| currencyFormat | object | - | Currency format with symbol and symbolPosition properties |
| visible | boolean | true | Whether column is visible in the table |
| customColumnName | string | - | Override column display name with a custom label |
| displayTypeIcon | boolean | false | Display data type icon next to column name |

### Conditional Formatting Object
Each item in the `conditional_formatting` array defines a formatting rule:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| column | string | Yes | Column name to apply formatting to |
| operator | string | Yes | Comparison operator: '<', '>', '<=', '>=', '==', '!=', 'between', 'not between' |
| targetValue | number | No | Value to compare against (required for single-value operators) |
| targetValueLeft | number | No | Left bound for 'between' and 'not between' operators |
| targetValueRight | number | No | Right bound for 'between' and 'not between' operators |
| colorScheme | string | No | Color scheme: 'Green', 'Red', or hex color code. For time comparison, special schemes available |
| toAllRow | boolean | No | Apply formatting to entire row instead of just the cell |
| toTextColor | boolean | No | Apply color to text instead of background |

### Example Request - Aggregate Mode with Totals
```json
{
  "slice_name": "Sales Summary by Region",
  "viz_type": "ag-grid-table",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"query_mode\": \"aggregate\", \"groupby\": [\"region\", \"product_category\"], \"metrics\": [\"sum__sales\", \"sum__profit\", \"count\"], \"percent_metrics\": [\"sum__sales\"], \"row_limit\": 1000, \"order_desc\": true, \"timeseries_limit_metric\": \"sum__sales\", \"show_totals\": true, \"table_timestamp_format\": \"smart_date\", \"page_length\": 20, \"include_search\": true, \"show_cell_bars\": true, \"color_pn\": true, \"align_pn\": false, \"column_config\": {\"sum__sales\": {\"d3NumberFormat\": \"$,.2f\", \"horizontalAlign\": \"right\"}, \"sum__profit\": {\"d3NumberFormat\": \"$,.2f\", \"horizontalAlign\": \"right\", \"colorPositiveNegative\": true}, \"count\": {\"d3NumberFormat\": \",d\"}}, \"conditional_formatting\": [{\"column\": \"sum__profit\", \"operator\": \"<\", \"targetValue\": 0, \"colorScheme\": \"#dc3545\", \"toTextColor\": false}]}",
  "description": "Sales and profit metrics grouped by region and category with conditional formatting",
  "owners": [1],
  "dashboards": [5]
}
```

### Example Request - Raw Mode with Column Reordering
```json
{
  "slice_name": "Recent Customer Orders",
  "viz_type": "ag-grid-table",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"query_mode\": \"raw\", \"all_columns\": [\"order_id\", \"customer_name\", \"customer_email\", \"order_date\", \"total_amount\", \"order_status\"], \"order_by_cols\": [[\"order_date\", false]], \"row_limit\": 100, \"table_timestamp_format\": \"%Y-%m-%d %H:%M:%S\", \"page_length\": 25, \"include_search\": true, \"allow_rearrange_columns\": true, \"column_config\": {\"total_amount\": {\"d3NumberFormat\": \"$,.2f\", \"horizontalAlign\": \"right\"}, \"order_date\": {\"columnWidth\": 180, \"d3TimeFormat\": \"%B %d, %Y %H:%M\"}, \"customer_email\": {\"columnWidth\": 250}, \"order_status\": {\"horizontalAlign\": \"center\"}}}",
  "description": "List of recent customer orders with customizable column layout",
  "owners": [1],
  "dashboards": [3]
}
```

### Example Request - Server Pagination for Large Dataset
```json
{
  "slice_name": "Transaction Browser",
  "viz_type": "ag-grid-table",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"query_mode\": \"raw\", \"all_columns\": [\"transaction_id\", \"timestamp\", \"user_id\", \"amount\", \"transaction_type\", \"status\"], \"server_pagination\": true, \"server_page_length\": 100, \"row_limit\": 100000, \"order_by_cols\": [[\"timestamp\", false]], \"include_search\": true, \"column_config\": {\"amount\": {\"d3NumberFormat\": \"$,.2f\", \"horizontalAlign\": \"right\"}, \"timestamp\": {\"d3TimeFormat\": \"%Y-%m-%d %H:%M:%S\", \"columnWidth\": 180}}}",
  "description": "High-performance browser for large transaction dataset with server-side pagination",
  "owners": [1]
}
```

### Example Request - Time Comparison with Color Indicators
```json
{
  "slice_name": "Revenue Metrics with Month-over-Month Comparison",
  "viz_type": "ag-grid-table",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"query_mode\": \"aggregate\", \"groupby\": [\"product_category\", \"region\"], \"metrics\": [\"sum__revenue\", \"sum__profit\"], \"time_compare\": [\"1 month ago\"], \"comparison_color_enabled\": true, \"comparison_color_scheme\": \"Green\", \"row_limit\": 500, \"show_cell_bars\": true, \"page_length\": 20, \"include_search\": true, \"conditional_formatting\": [{\"column\": \"Main sum__revenue\", \"operator\": \">\", \"targetValue\": 100000, \"colorScheme\": \"Green\"}], \"column_config\": {\"Main sum__revenue\": {\"d3NumberFormat\": \"$,.0f\", \"horizontalAlign\": \"right\"}, \"# sum__revenue\": {\"d3NumberFormat\": \"$+,.0f\", \"horizontalAlign\": \"right\"}, \"% sum__revenue\": {\"d3NumberFormat\": \".1%\", \"horizontalAlign\": \"right\"}}}",
  "description": "Product and region revenue with month-over-month comparison and visual indicators",
  "owners": [1],
  "dashboards": [7]
}
```

### Example Request - Advanced Conditional Formatting
```json
{
  "slice_name": "KPI Dashboard with Thresholds",
  "viz_type": "ag-grid-table",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"query_mode\": \"aggregate\", \"groupby\": [\"department\"], \"metrics\": [\"avg__satisfaction_score\", \"sum__complaints\", \"avg__response_time_hours\"], \"row_limit\": 100, \"show_cell_bars\": true, \"align_pn\": false, \"color_pn\": true, \"page_length\": 20, \"conditional_formatting\": [{\"column\": \"avg__satisfaction_score\", \"operator\": \"<\", \"targetValue\": 3.5, \"colorScheme\": \"#dc3545\"}, {\"column\": \"avg__satisfaction_score\", \"operator\": \">=\", \"targetValue\": 4.5, \"colorScheme\": \"#28a745\"}, {\"column\": \"sum__complaints\", \"operator\": \">\", \"targetValue\": 10, \"colorScheme\": \"#ffc107\", \"toAllRow\": true}, {\"column\": \"avg__response_time_hours\", \"operator\": \"between\", \"targetValueLeft\": 0, \"targetValueRight\": 2, \"colorScheme\": \"#28a745\"}], \"column_config\": {\"avg__satisfaction_score\": {\"d3NumberFormat\": \".2f\", \"horizontalAlign\": \"center\", \"customColumnName\": \"Satisfaction\"}, \"sum__complaints\": {\"d3NumberFormat\": \",d\", \"horizontalAlign\": \"center\", \"customColumnName\": \"Total Complaints\"}, \"avg__response_time_hours\": {\"d3NumberFormat\": \".1f\", \"horizontalAlign\": \"center\", \"customColumnName\": \"Avg Response Time (hrs)\"}}}",
  "description": "Department KPIs with multi-level threshold-based conditional formatting",
  "owners": [1]
}
```

## Parameter Details

### Query Modes
The AG Grid Table chart supports two distinct query modes:

#### Aggregate Mode (`query_mode: "aggregate"`)
- Uses GROUP BY to aggregate data
- Requires at least one of: `groupby`, `metrics`, or `percent_metrics`
- Supports `timeseries_limit_metric` for ordering results
- Allows `show_totals` to display summary row with aggregated values
- Enables time comparison features for trend analysis
- Best for summary views and analytics

#### Raw Mode (`query_mode: "raw"`)
- Returns individual records without aggregation
- Requires `all_columns` to specify which columns to display
- Uses `order_by_cols` for sorting in format [[column, is_ascending]]
- Does not support metrics, groupby, time comparison, or totals
- Best for detailed record views and data exploration

### Time Granularity Options
The `time_grain_sqla` field accepts ISO 8601 duration strings and becomes visible when grouping by datetime columns:
- `PT1S` - 1 second
- `PT5S` - 5 seconds
- `PT30S` - 30 seconds
- `PT1M` - 1 minute
- `PT5M` - 5 minutes
- `PT10M` - 10 minutes
- `PT15M` - 15 minutes
- `PT30M` - 30 minutes
- `PT1H` - 1 hour
- `PT6H` - 6 hours
- `P1D` - 1 day
- `P7D` - 7 days
- `P1W` - week
- `P1M` - month
- `P3M` - quarter
- `P1Y` - year

### Pagination Options
Three pagination modes are available:

#### No Pagination
- Set `page_length` to `0` or `null`
- All rows displayed at once (up to `row_limit`)
- Best for small datasets or when all data needs to be visible

#### Client-Side Pagination
- Set `page_length` to desired number of rows per page: 10, 20, 50, 100, or 200
- All data loaded upfront, pagination handled in browser by AG Grid
- Faster page navigation but initial load includes all data
- Best for datasets under 10,000 rows

#### Server-Side Pagination
- Set `server_pagination` to `true`
- Set `server_page_length` to rows per page: 10, 20, 50, 100, or 200
- Only requested page loaded from server
- Better for very large datasets (reduces initial load time and memory usage)
- Experimental feature with advanced capabilities

### Number Format Patterns
The `d3NumberFormat` field accepts D3 format strings:
- `,d` - Comma-separated integers (e.g., 1,234)
- `.2f` - Fixed decimal with 2 places (e.g., 123.45)
- `.3s` - SI-prefix with 3 significant digits (e.g., 1.23k)
- `.2%` - Percentage with 2 decimal places (e.g., 12.34%)
- `$,.2f` - Currency format (e.g., $1,234.56)
- `+,.2f` - Explicit plus sign for positive numbers (e.g., +123.45)
- `SMART_NUMBER` - Automatically choose appropriate format

### Date Format Patterns
The `table_timestamp_format` and `d3TimeFormat` fields accept:
- `smart_date` - Automatically format based on granularity (default, recommended)
- `%Y-%m-%d` - ISO date (e.g., 2024-01-15)
- `%Y-%m-%d %H:%M:%S` - ISO datetime (e.g., 2024-01-15 14:30:00)
- `%B %d, %Y` - Long format (e.g., January 15, 2024)
- `%m/%d/%Y` - US format (e.g., 01/15/2024)
- `%Y-%m-%d %H:%M` - Datetime without seconds (e.g., 2024-01-15 14:30)
- Any D3 time format string

### Conditional Formatting Operators
- `<` - Less than
- `>` - Greater than
- `<=` - Less than or equal to
- `>=` - Greater than or equal to
- `==` - Equal to
- `!=` - Not equal to
- `between` - Between two values (inclusive, requires targetValueLeft and targetValueRight)
- `not between` - Not between two values (requires targetValueLeft and targetValueRight)

### Color Schemes for Conditional Formatting
- **Named schemes**: `'Green'`, `'Red'` (for time comparison)
  - `'Green'`: Increase is green, decrease is red (typical for revenue/positive metrics)
  - `'Red'`: Increase is red, decrease is green (typical for costs/negative metrics)
- **Hex color codes**: e.g., `'#28a745'` (green), `'#dc3545'` (red), `'#ffc107'` (yellow)
- **Standard Superset color schemes**: Various categorical and sequential color palettes

### Time Comparison
When `time_compare` is set with a time period:
- Each numeric metric generates four columns:
  - **Main [metric]**: The main metric value for the current period
  - **# [metric]**: Absolute change from comparison period (e.g., +500)
  - **△ [metric]**: Relative change percentage (e.g., 25%)
  - **% [metric]**: Percentage contribution to total
- Use `comparison_color_enabled` to add visual indicators:
  - Arrows (↑ for increase, ↓ for decrease) in main column
  - Color coding based on `comparison_color_scheme`
- `comparison_color_scheme` controls interpretation:
  - `'Green'`: Increase shown as positive (green arrow), decrease as negative (red arrow)
  - `'Red'`: Increase shown as negative (red arrow), decrease as positive (green arrow)
- Column configuration should target the generated column names (e.g., "Main sum__revenue")
- Basic conditional formatting can be overwritten by custom conditional formatting rules

### Row Limit Guidelines
- **Default**: 1,000 rows (changed from standard table's 10,000 for better performance)
- **Available options**: 10, 50, 100, 250, 500, 1000, 5000, 10000, 50000, 100000, 150000, 200000, 250000, 300000, 350000, 400000, 450000, 500000
- **Maximum varies** based on server configuration:
  - Without server pagination: limited by `SQL_MAX_ROW` config
  - With server pagination: can query larger datasets up to `TABLE_VIZ_MAX_ROW_SERVER` config
- **Validation**: row_limit must be an integer and cannot exceed configured maximum
- For very large tables, enable server pagination to improve performance and reduce memory usage

### Percentage Metrics
- `percent_metrics` calculates each metric as a percentage of the column total
- Percentages are calculated only from data within the row limit (not all records)
- Particularly useful for contribution analysis (e.g., "Region A represents 35% of total sales")
- Display with `d3NumberFormat: ".2%"` for proper percentage formatting
- Can be combined with regular metrics to show both absolute and relative values

### Show Summary/Totals
- When `show_totals` is `true`, displays a summary row with aggregated totals
- Only available in aggregate mode
- Note: Row limit does not apply to the totals calculation - totals are computed across all data
- Totals row appears at the bottom of the table
- Useful for showing grand totals in reports and dashboards

## Best Practices

### Performance Optimization
1. **Row limits**: Use appropriate `row_limit` values - don't fetch more data than needed. AG Grid Table defaults to 1,000 rows
2. **Server pagination**: Enable for datasets with >5,000 rows to reduce initial load time and memory usage
3. **Caching**: Set `cache_timeout` for data that doesn't change frequently to reduce database load
4. **Query mode**: Use aggregate mode instead of raw mode when possible to reduce data volume
5. **Indexing**: Index columns used in `order_by_cols` or `timeseries_limit_metric` in your database
6. **Column visibility**: Hide unnecessary columns using `column_config[column].visible: false` instead of removing them

### User Experience
1. **Search**: Enable `include_search` for tables with >20 rows to help users find data quickly
2. **Pagination**: Use `page_length` of 20-50 for optimal readability (not too long, not too short)
3. **Column configuration**: Configure `column_config` to set appropriate widths, alignments, and custom names
4. **Column reordering**: Use `allow_rearrange_columns` in exploratory dashboards but consider disabling in fixed reports for consistency
5. **Custom labels**: Set meaningful `customColumnName` values to replace technical column names with business-friendly terms
6. **Search box placement**: The search box appears at the top of the table when enabled

### Visual Clarity
1. **Cell bars**: Use `show_cell_bars` selectively - best for columns where relative magnitude matters
2. **Color coding**: Enable `color_pn` to quickly identify positive/negative values in financial and performance metrics
3. **Conditional formatting**: Use sparingly to highlight exceptions rather than coloring everything - focus on thresholds and KPIs
4. **Numeric alignment**: Align numeric columns to the right (`horizontalAlign: "right"`) for easier comparison
5. **Text truncation**: Use `truncateLongCells` for long text columns to maintain table compactness and readability
6. **Cell bar alignment**: Enable `align_pn` for metrics that include both positive and negative values to show proportions clearly

### Data Integrity
1. **Query mode validation**: Always validate that `query_mode` matches your data requirements (aggregate vs raw)
2. **Required fields**: In aggregate mode, ensure at least one of `groupby`, `metrics`, or `percent_metrics` has values
3. **Raw mode columns**: In raw mode, ensure `all_columns` is populated with valid column names
4. **Time comparison**: When using time comparison, ensure your metrics are summable/comparable across time periods
5. **Conditional formatting**: Test rules with edge cases (nulls, zeros, very large/small numbers, boundary values)
6. **Sort ordering**: Use proper format for `order_by_cols`: array of [column_name, is_ascending] tuples

### Advanced Features
1. **Time comparison naming**: When using time comparison, reference generated column names in `column_config` (e.g., "Main sum__revenue", "# sum__revenue")
2. **Basic vs custom formatting**: Basic conditional formatting (via `comparison_color_enabled`) can be overridden by custom `conditional_formatting` rules
3. **Row-level formatting**: Use `toAllRow: true` in conditional formatting to highlight entire rows based on cell values
4. **Temporal granularity**: Use `temporal_columns_lookup` for fine-grained control of time granularity per column
5. **Mixed formatting**: Combine cell bars, conditional formatting, and time comparison for rich visual analytics

## Differences from Standard Table Chart

The AG Grid Table (`ag-grid-table`) is the next-generation table visualization with several improvements over the standard table chart:

### Performance
- **Better rendering**: AG Grid provides superior performance for large datasets with virtual scrolling
- **Smoother interactions**: Enhanced scrolling, sorting, and filtering performance
- **Lower default row limit**: Defaults to 1,000 rows (vs 10,000 for standard table) for better initial performance

### Features
- **Advanced grid**: Built on enterprise-grade AG Grid library with professional features
- **Enhanced filtering**: More sophisticated filtering capabilities
- **Modern UI**: Updated visual design following current design standards
- **Better column management**: Improved column resizing and reordering experience

### Compatibility
- **Same API**: Uses identical params structure as standard table for easy migration
- **Control panel**: Shares most control panel options with standard table
- **Visualization name**: Known as "Table V2" in the UI

### Migration Path
Most standard table configurations work directly with AG Grid Table by simply changing `viz_type` from `table` to `ag-grid-table`.
