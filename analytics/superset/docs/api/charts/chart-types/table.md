# Table (`table`)

## Description
The Table chart displays data in a classic row-by-column spreadsheet format. This visualization provides a tabular view of your dataset with extensive customization options including sorting, pagination, search functionality, conditional formatting, and visual enhancements like cell bars. Tables are versatile and can show both raw data records and aggregated metrics, making them suitable for detailed data exploration and reporting.

## When to Use
Use this chart when you need to present data in a structured, readable format that allows users to see individual records or aggregated values in detail. Tables are ideal when precise values matter more than visual patterns, or when you need to present multiple metrics and dimensions together. The table chart supports both aggregate queries (with GROUP BY) and raw data queries, offering flexibility for different analytical needs.

## Example Use Cases
- Displaying detailed sales records with customer information, order amounts, and dates
- Creating executive summary reports with aggregated metrics grouped by region or time period
- Building searchable product catalogs with multiple attributes (name, price, category, stock)
- Showing user activity logs with timestamps, actions, and details
- Presenting comparison tables with metrics across different dimensions using time comparison features
- Creating paginated data browsers for large datasets with server-side pagination
- Displaying financial statements with conditional formatting to highlight positive/negative values

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `table` |
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
| groupby | array | No | [] | Columns to group by (only in aggregate mode) |
| metrics | array | No | [] | Metrics to display (only in aggregate mode) |
| all_columns | array | No | [] | Columns to display (only in raw mode) |
| percent_metrics | array | No | [] | Metrics to display as percentages of total (only in aggregate mode) |
| percent_metric_calculation | string | No | 'row_limit' | How to calculate percentage metrics: 'row_limit' or 'all_records' |
| adhoc_filters | array | No | [] | Filters to apply to the data |
| time_grain_sqla | string | No | null | Time granularity when grouping by temporal columns (e.g., 'P1D', 'P1W', 'P1M') |
| temporal_columns_lookup | object | No | {} | Mapping of columns to their temporal granularities |
| timeseries_limit_metric | string/object | No | null | Metric to use for ordering results (aggregate mode only) |
| order_by_cols | array | No | [] | Columns to order results by (raw mode only) |
| order_desc | boolean | No | true | Sort in descending order (aggregate mode with timeseries_limit_metric) |
| row_limit | integer | No | 10000 | Maximum number of rows to return |
| server_pagination | boolean | No | false | Enable server-side pagination (experimental) |
| server_page_length | integer | No | 10 | Number of rows per page for server pagination |
| show_totals | boolean | No | false | Show summary row with totals (aggregate mode only) |
| table_timestamp_format | string | No | 'smart_date' | D3 time format for datetime columns |
| page_length | integer/string | No | null | Client-side rows per page (0 or null means no pagination) |
| include_search | boolean | No | false | Include client-side search box |
| allow_rearrange_columns | boolean | No | false | Allow users to drag-and-drop column headers to reorder |
| allow_render_html | boolean | No | true | Render table cells as HTML when applicable (e.g., hyperlinks) |
| column_config | object | No | {} | Per-column customization settings (see Column Config section) |
| show_cell_bars | boolean | No | true | Display background bar charts in table columns |
| align_pn | boolean | No | false | Align background charts with both positive and negative values at 0 |
| color_pn | boolean | No | true | Colorize numeric values by whether they are positive or negative |
| conditional_formatting | array | No | [] | Custom conditional formatting rules (see Conditional Formatting section) |
| comparison_color_enabled | boolean | No | false | Enable basic conditional formatting for time comparison columns |
| comparison_color_scheme | string | No | 'Green' | Color scheme for comparison: 'Green' (increase=green) or 'Red' (increase=red) |
| time_compare | string | No | null | Time period to compare against (e.g., '1 week ago', '1 month ago') |

### Column Config Object
The `column_config` field allows per-column customization with keys being column names and values being objects with these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| d3NumberFormat | string | - | D3 number format string for numeric columns |
| d3SmallNumberFormat | string | - | Format for small numbers (e.g., percentages) |
| d3TimeFormat | string | - | D3 time format string for datetime columns |
| columnWidth | number | - | Column width in pixels |
| horizontalAlign | string | 'left' | Horizontal alignment: 'left', 'right', or 'center' |
| showCellBars | boolean | true | Show cell bars for this column |
| alignPositiveNegative | boolean | false | Align cell bars at zero for this column |
| colorPositiveNegative | boolean | true | Color code positive/negative values for this column |
| truncateLongCells | boolean | false | Truncate long cell content with ellipsis |
| currencyFormat | object | - | Currency format with symbol and symbolPosition |
| visible | boolean | true | Whether column is visible |
| customColumnName | string | - | Override column display name |
| displayTypeIcon | boolean | false | Display data type icon next to column name |

### Conditional Formatting Object
Each item in the `conditional_formatting` array defines a formatting rule:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| column | string | Yes | Column name to apply formatting to |
| operator | string | Yes | Comparison operator: '<', '>', '<=', '>=', '==', '!=', 'between', 'not between' |
| targetValue | number | No | Value to compare against (not used for 'between' operators) |
| targetValueLeft | number | No | Left bound for 'between' operators |
| targetValueRight | number | No | Right bound for 'between' operators |
| colorScheme | string | No | Color scheme: 'Green', 'Red', or standard Superset color scheme |
| toAllRow | boolean | No | Apply formatting to entire row (vs just the cell) |
| toTextColor | boolean | No | Apply color to text (vs background) |

### Example Request - Aggregate Mode
```json
{
  "slice_name": "Sales by Region",
  "viz_type": "table",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"query_mode\": \"aggregate\", \"groupby\": [\"region\", \"category\"], \"metrics\": [\"sum__sales\", \"count\"], \"percent_metrics\": [\"sum__sales\"], \"row_limit\": 1000, \"order_desc\": true, \"timeseries_limit_metric\": \"sum__sales\", \"show_totals\": true, \"table_timestamp_format\": \"smart_date\", \"page_length\": 20, \"include_search\": true, \"show_cell_bars\": true, \"color_pn\": true, \"align_pn\": false, \"column_config\": {\"sum__sales\": {\"d3NumberFormat\": \"$,.2f\", \"horizontalAlign\": \"right\"}, \"count\": {\"d3NumberFormat\": \",d\"}}, \"conditional_formatting\": [{\"column\": \"sum__sales\", \"operator\": \">\", \"targetValue\": 100000, \"colorScheme\": \"#28a745\"}]}",
  "description": "Sales metrics grouped by region and category with conditional formatting",
  "owners": [1],
  "dashboards": [5]
}
```

### Example Request - Raw Mode
```json
{
  "slice_name": "Recent Orders",
  "viz_type": "table",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"query_mode\": \"raw\", \"all_columns\": [\"order_id\", \"customer_name\", \"order_date\", \"total_amount\", \"status\"], \"order_by_cols\": [[\"order_date\", false]], \"row_limit\": 100, \"table_timestamp_format\": \"%Y-%m-%d %H:%M:%S\", \"page_length\": 25, \"include_search\": true, \"allow_rearrange_columns\": true, \"allow_render_html\": true, \"column_config\": {\"total_amount\": {\"d3NumberFormat\": \"$,.2f\", \"horizontalAlign\": \"right\"}, \"order_date\": {\"columnWidth\": 150}}}",
  "description": "List of recent orders with customer details",
  "owners": [1],
  "dashboards": [3]
}
```

### Example Request - Server Pagination
```json
{
  "slice_name": "Large Dataset Browser",
  "viz_type": "table",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"query_mode\": \"raw\", \"all_columns\": [\"id\", \"name\", \"email\", \"created_at\"], \"server_pagination\": true, \"server_page_length\": 50, \"row_limit\": 10000, \"order_by_cols\": [[\"created_at\", false]], \"include_search\": false, \"allow_render_html\": false}",
  "description": "Paginated view of large dataset using server-side pagination",
  "owners": [1]
}
```

### Example Request - Time Comparison
```json
{
  "slice_name": "Metrics with Time Comparison",
  "viz_type": "table",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"query_mode\": \"aggregate\", \"groupby\": [\"product_category\"], \"metrics\": [\"sum__revenue\", \"count__orders\"], \"time_compare\": [\"1 month ago\"], \"comparison_color_enabled\": true, \"comparison_color_scheme\": \"Green\", \"row_limit\": 500, \"show_cell_bars\": true, \"conditional_formatting\": [{\"column\": \"Main sum__revenue\", \"operator\": \">\", \"targetValue\": 50000, \"colorScheme\": \"Green\"}]}",
  "description": "Product metrics with month-over-month comparison",
  "owners": [1],
  "dashboards": [7]
}
```

## Parameter Details

### Query Modes
The table chart supports two distinct query modes:

#### Aggregate Mode (`query_mode: "aggregate"`)
- Uses GROUP BY to aggregate data
- Requires at least one of: `groupby`, `metrics`, or `percent_metrics`
- Supports `timeseries_limit_metric` for ordering results
- Allows `show_totals` to display summary row
- Enables time comparison features

#### Raw Mode (`query_mode: "raw"`)
- Returns individual records without aggregation
- Requires `all_columns` to specify which columns to display
- Uses `order_by_cols` for sorting
- Does not support metrics, groupby, or time comparison

### Time Granularity Options
The `time_grain_sqla` field accepts ISO 8601 duration strings:
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

#### Client-Side Pagination
- Set `page_length` to desired number of rows per page (e.g., 10, 20, 50, 100)
- All data loaded upfront, pagination handled in browser
- Faster page navigation but initial load includes all data

#### Server-Side Pagination
- Set `server_pagination` to `true`
- Set `server_page_length` to rows per page
- Only requested page loaded from server
- Better for very large datasets (reduces initial load time)
- Experimental feature

### Number Format Patterns
The `d3NumberFormat` field accepts D3 format strings:
- `,d` - Comma-separated integers (e.g., 1,234)
- `.2f` - Fixed decimal with 2 places (e.g., 123.45)
- `.3s` - SI-prefix with 3 significant digits (e.g., 1.23k)
- `.2%` - Percentage with 2 decimal places (e.g., 12.34%)
- `$,.2f` - Currency format (e.g., $1,234.56)
- `SMART_NUMBER` - Automatically choose appropriate format

### Date Format Patterns
The `table_timestamp_format` and `d3TimeFormat` fields accept:
- `smart_date` - Automatically format based on granularity (default)
- `%Y-%m-%d` - ISO date (e.g., 2024-01-15)
- `%Y-%m-%d %H:%M:%S` - ISO datetime (e.g., 2024-01-15 14:30:00)
- `%B %d, %Y` - Long format (e.g., January 15, 2024)
- `%m/%d/%Y` - US format (e.g., 01/15/2024)
- Any D3 time format string

### Conditional Formatting Operators
- `<` - Less than
- `>` - Greater than
- `<=` - Less than or equal to
- `>=` - Greater than or equal to
- `==` - Equal to
- `!=` - Not equal to
- `between` - Between two values (inclusive)
- `not between` - Not between two values

### Color Schemes for Conditional Formatting
- Named schemes: `'Green'`, `'Red'`
- Standard Superset color schemes (various categorical and sequential options)
- Hex color codes (e.g., `'#28a745'`)

### Time Comparison
When `time_compare` is set:
- Each metric generates four columns: Main, # (absolute change), △ (relative change), % (percentage change)
- Use `comparison_color_enabled` to add visual indicators (arrows and colors)
- `comparison_color_scheme` controls whether increase is shown as positive (Green) or negative (Red)
- Column configuration should target the generated column names (e.g., "Main sum__revenue")

### Row Limit Guidelines
- Default: 10,000 rows
- Maximum varies based on server configuration
- Without server pagination: limited by `SQL_MAX_ROW` config (typically 50,000-100,000)
- With server pagination: can query larger datasets up to `TABLE_VIZ_MAX_ROW_SERVER` config
- For very large tables, enable server pagination to improve performance

### Percentage Metrics
- `percent_metrics` calculates each metric as a percentage of the column total
- Use `percent_metric_calculation` to control denominator:
  - `'row_limit'`: Percentage of rows within the row limit (default)
  - `'all_records'`: Percentage of all records (ignores row limit)
- Particularly useful for showing contribution analysis (e.g., "Region A represents 35% of total sales")

## Best Practices

### Performance Optimization
1. Use appropriate `row_limit` values - don't fetch more data than needed
2. Enable server pagination for datasets with >1000 rows
3. Set `cache_timeout` for data that doesn't change frequently
4. Use aggregate mode instead of raw mode when possible to reduce data volume
5. Index columns used in `order_by_cols` or `timeseries_limit_metric` in your database

### User Experience
1. Enable `include_search` for tables with >20 rows to help users find data
2. Use `page_length` of 20-50 for optimal readability (not too long, not too short)
3. Configure `column_config` to set appropriate widths and alignments
4. Use `allow_rearrange_columns` in exploratory dashboards but consider disabling in fixed reports
5. Set meaningful `customColumnName` values to replace technical column names

### Visual Clarity
1. Use `show_cell_bars` sparingly - best for columns where relative magnitude matters
2. Enable `color_pn` to quickly identify positive/negative values
3. Use conditional formatting to highlight exceptions rather than coloring everything
4. Align numeric columns to the right (`horizontalAlign: "right"`) for easier comparison
5. Truncate long text columns with `truncateLongCells` to maintain table compactness

### Data Integrity
1. Always validate that `query_mode` matches your data requirements (aggregate vs raw)
2. In aggregate mode, ensure at least one of `groupby`, `metrics`, or `percent_metrics` has values
3. In raw mode, ensure `all_columns` is populated
4. When using time comparison, ensure your metrics are summable/comparable across time periods
5. Test conditional formatting rules with edge cases (nulls, zeros, very large/small numbers)
