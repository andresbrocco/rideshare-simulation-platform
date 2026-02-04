# Heatmap (`heatmap_v2`)

## Description
The Heatmap visualization uses color intensity to represent metric values across pairs of dimensions. This chart excels at showcasing the correlation or strength between two groups by displaying data in a matrix format where each cell's color represents the magnitude of the metric. Built with Apache ECharts, this visualization provides interactive features and smooth rendering for exploring relationships in your data.

## When to Use
Use a heatmap when you need to visualize the relationship between two categorical dimensions with a quantitative metric. This chart type is particularly effective for identifying patterns, correlations, and outliers across multiple categories. The color-coding makes it easy to spot high and low values at a glance, and normalization options help compare relative values within rows, columns, or across the entire dataset.

## Example Use Cases
- Displaying sales performance across product categories and regions to identify top-performing combinations
- Analyzing website traffic patterns by day of week and hour of day to optimize content publishing schedules
- Visualizing correlation matrices between multiple variables in data science and statistical analysis
- Tracking employee productivity across departments and time periods to identify trends
- Monitoring system performance metrics across different servers and time intervals
- Comparing customer satisfaction scores across service types and demographic segments

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `heatmap_v2` |
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
| x_axis | string | Yes | - | Column to use for the X-axis dimension |
| groupby | string | Yes | - | Column to use for the Y-axis dimension (single value only) |
| metric | string/object | Yes | - | Metric to display as cell values and color intensity |
| time_grain_sqla | string | No | 'P1D' | Time granularity when X-axis is a temporal column (e.g., 'P1D' for 1 day, 'P1W' for 1 week) |
| adhoc_filters | array | No | [] | Filters to apply to the data |
| row_limit | integer | No | 10000 | Maximum number of rows to compute in the source query |
| sort_x_axis | string | No | - | Sort order for X-axis ('alpha_asc', 'alpha_desc', 'value_asc', 'value_desc') |
| sort_y_axis | string | No | - | Sort order for Y-axis ('alpha_asc', 'alpha_desc', 'value_asc', 'value_desc') |
| normalize_across | string | No | 'heatmap' | Normalization scope ('heatmap', 'x', 'y') |
| legend_type | string | No | 'continuous' | Type of legend to display ('continuous' or 'piecewise') |
| linear_color_scheme | string | No | (default) | Color scheme to use for the heatmap gradient |
| border_color | object | No | {"r": 0, "g": 0, "b": 0, "a": 1} | RGBA color object for cell borders |
| border_width | number | No | 0 | Width of cell borders in pixels (0-2, step 0.1) |
| xscale_interval | integer | No | -1 | Number of steps between X-axis ticks (-1 for auto) |
| yscale_interval | integer | No | -1 | Number of steps between Y-axis ticks (-1 for auto) |
| left_margin | string/integer | No | 'auto' | Left margin in pixels for axis labels ('auto', 50, 75, 100, 125, 150, 200) |
| bottom_margin | string/integer | No | 'auto' | Bottom margin in pixels for axis labels ('auto', 50, 75, 100, 125, 150, 200) |
| value_bounds | array | No | [null, null] | Hard min/max bounds for color coding [min, max] |
| y_axis_format | string | No | 'SMART_NUMBER' | Number format for cell values (e.g., '.2f', '.3s', ',d') |
| x_axis_time_format | string | No | 'smart_date' | Date format for X-axis when temporal (e.g., '%Y-%m-%d', '%B %d, %Y') |
| xAxisLabelRotation | integer | No | 0 | Rotation angle for X-axis labels in degrees (e.g., 0, 45, 90) |
| currency_format | object | No | - | Currency format configuration with symbol and placement |
| show_legend | boolean | No | true | Whether to display the color legend |
| show_percentage | boolean | No | true | Whether to include percentage in cell tooltips |
| show_values | boolean | No | false | Whether to display numeric values within cells |
| normalized | boolean | No | false | Whether to apply normal distribution based on rank for color scaling |

### Example Request
```json
{
  "slice_name": "Sales by Product and Region",
  "viz_type": "heatmap_v2",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"x_axis\": \"region\", \"groupby\": \"product_category\", \"metric\": \"sum__sales_amount\", \"normalize_across\": \"heatmap\", \"legend_type\": \"continuous\", \"linear_color_scheme\": \"blue_white_yellow\", \"show_values\": true, \"show_percentage\": true, \"y_axis_format\": \"$,.0f\", \"xAxisLabelRotation\": 45, \"left_margin\": 100, \"bottom_margin\": 100, \"sort_x_axis\": \"value_desc\", \"sort_y_axis\": \"alpha_asc\", \"show_legend\": true, \"border_width\": 0.5, \"border_color\": {\"r\": 200, \"g\": 200, \"b\": 200, \"a\": 1}, \"row_limit\": 10000}",
  "description": "Heatmap showing total sales across product categories and regions with normalized color intensity",
  "owners": [1],
  "dashboards": [5]
}
```

## Parameter Details

### Time Granularity Options
The `time_grain_sqla` field accepts the following values when X-axis is a temporal column:
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

### Sort Options
Both `sort_x_axis` and `sort_y_axis` accept the following values:
- `alpha_asc` - Sort alphabetically ascending (A to Z)
- `alpha_desc` - Sort alphabetically descending (Z to A)
- `value_asc` - Sort by metric value ascending (smallest to largest)
- `value_desc` - Sort by metric value descending (largest to smallest)

### Normalization Modes
The `normalize_across` field determines how color intensity is calculated:
- `heatmap` - Values are normalized across the entire heatmap (0% to 100% of all cells)
- `x` - Values are normalized within each column independently
- `y` - Values are normalized within each row independently

This is useful for emphasizing relative differences within specific dimensions rather than absolute values across the entire dataset.

### Legend Types
The `legend_type` field controls the legend display:
- `continuous` - Shows a smooth gradient color bar (default)
- `piecewise` - Shows discrete color ranges with defined breakpoints

### Color Schemes
The `linear_color_scheme` field uses sequential color schemes from the Superset color scheme registry. Common options include:
- `blue_white_yellow` - Blue (low) to white (mid) to yellow (high)
- `fire` - Dark red to bright yellow gradient
- `white_black` - White (low) to black (high)
- `black_white` - Black (low) to white (high)
- `superset_seq_1` through `superset_seq_10` - Various sequential palettes

The default is determined by your Superset configuration. Sequential schemes are designed for ordered data where darker or more saturated colors represent higher values.

### Number Format Patterns
The `y_axis_format` field accepts D3 format strings:
- `,d` - Comma-separated integers (e.g., 1,234)
- `.2f` - Fixed decimal with 2 places (e.g., 123.45)
- `.3s` - SI-prefix with 3 significant digits (e.g., 1.23k)
- `.2%` - Percentage with 2 decimal places (e.g., 12.34%)
- `$,.2f` - Currency format (e.g., $1,234.56)
- `SMART_NUMBER` - Automatically formats large numbers with SI prefixes

### Date Format Patterns
The `x_axis_time_format` field accepts D3 time format strings when X-axis is temporal:
- `%Y-%m-%d` - ISO date format (2024-01-15)
- `%B %d, %Y` - Full month name (January 15, 2024)
- `%m/%d/%Y` - US date format (01/15/2024)
- `%Y-%m-%d %H:%M:%S` - Date and time (2024-01-15 14:30:00)
- `smart_date` - Automatically formats based on time granularity (default)

### Border Styling
Configure cell borders for better visual separation:
- `border_width`: Set to 0 for no borders, or up to 2 pixels for visible borders
- `border_color`: RGBA color object with properties `r`, `g`, `b` (0-255), and `a` (0-1 for opacity)

Example: `{"r": 200, "g": 200, "b": 200, "a": 1}` creates a light gray border

### Value Bounds
The `value_bounds` array allows you to set fixed min/max values for color coding:
- `[null, null]` - Auto-scale based on data (default)
- `[0, 100]` - Fix scale from 0 to 100
- `[null, 1000]` - Auto-scale minimum, fix maximum at 1000
- `[10, null]` - Fix minimum at 10, auto-scale maximum

This is useful for maintaining consistent color scales across multiple heatmaps or time periods.

### Display Options
Control what information is shown in the visualization:
- `show_legend`: Toggle the color legend on/off
- `show_percentage`: Include percentage of max value in cell tooltips
- `show_values`: Display the numeric value directly inside each cell (may clutter small cells)
- `normalized`: Apply rank-based normal distribution to color scaling for better visual separation

### Axis Label Rotation
The `xAxisLabelRotation` field accepts any integer degree value:
- `0` - Horizontal labels (default)
- `45` - Diagonal labels (good for medium-length labels)
- `90` - Vertical labels (good for long labels or many categories)
- Custom values like `30` or `60` are also supported

### Margins
Adjust `left_margin` and `bottom_margin` to provide more space for axis labels:
- Use `'auto'` to let the chart calculate appropriate spacing
- Use numeric values (50, 75, 100, 125, 150, 200) for fixed pixel margins
- Increase margins when using long category names or rotated labels

### Scale Intervals
The `xscale_interval` and `yscale_interval` fields control axis tick density:
- `-1` - Automatic interval (default, shows reasonable number of ticks)
- `1` - Show every label
- `2` - Show every other label
- Higher values show fewer labels (useful for high-cardinality dimensions)

## Best Practices

1. **Dimension Cardinality**: Heatmaps work best with moderate cardinality (5-50 categories per dimension). Too few categories underutilize the format, while too many make cells too small to distinguish.

2. **Normalization Strategy**: Choose normalization based on your analysis goal:
   - Use `heatmap` normalization to compare all cells against each other
   - Use `x` normalization to compare performance within each column
   - Use `y` normalization to compare performance within each row

3. **Color Scheme Selection**: Choose color schemes that match your data's meaning:
   - Use diverging schemes (blue-white-red) for data with a meaningful midpoint
   - Use sequential schemes (white-to-blue) for data with only one direction of change
   - Consider colorblind-friendly palettes for accessibility

4. **Label Management**: For readability with many categories:
   - Rotate X-axis labels 45° or 90° to prevent overlap
   - Adjust margins to accommodate rotated labels
   - Use scale intervals to show fewer labels
   - Consider sorting by value to group similar items together

5. **Value Display**: Only enable `show_values` when you have moderate cell counts and sufficient cell size. For dense heatmaps, rely on the tooltip and color encoding instead.

6. **Performance**: Use `row_limit` to constrain large queries. Heatmaps with thousands of cells may render slowly in the browser.
