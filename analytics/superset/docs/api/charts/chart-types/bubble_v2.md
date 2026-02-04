# Bubble Chart (`bubble_v2`)

## Description
The Bubble Chart visualizes data across three dimensions in a single chart: X-axis position, Y-axis position, and bubble size. Each bubble represents a data point, with its position determined by X and Y values and its size determined by a metric. Bubbles can be grouped and colored by series to show relationships across an additional dimension, making it ideal for multi-dimensional correlation analysis.

## When to Use
Use a Bubble Chart when you need to display relationships between three or more quantitative variables simultaneously. It's particularly effective for identifying patterns, clusters, and outliers across multiple dimensions. The chart works best when you have a moderate number of data points that won't overcrowd the visualization space.

## Example Use Cases
- Analyzing product performance by plotting price (X-axis) vs. sales volume (Y-axis) with bubble size representing profit margin, grouped by product category
- Comparing countries by GDP per capita (X-axis) vs. life expectancy (Y-axis) with population as bubble size, colored by continent
- Evaluating marketing campaigns by cost (X-axis) vs. reach (Y-axis) with conversion rate as bubble size, grouped by channel
- Visualizing website metrics by plotting page load time (X-axis) vs. bounce rate (Y-axis) with traffic volume as bubble size, colored by device type
- Examining real estate properties by square footage (X-axis) vs. price (Y-axis) with number of bedrooms as bubble size, grouped by neighborhood

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `bubble_v2` |
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
The `params` field must be a JSON string containing an object with the following fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| series | string/object | No | null | Dimension to group bubbles by. Each series is represented by a specific color. Can be a column name or metric object. |
| entity | string/object | Yes | null | The entity/dimension to be plotted. Each entity becomes a bubble on the chart. Must be a column name or dimension. |
| x | object | Yes | null | Metric or column for X-axis values. Must be a metric object with aggregation function. |
| y | object | Yes | null | Metric or column for Y-axis values. Must be a metric object with aggregation function. |
| size | object | No | null | Metric used to calculate bubble size. Larger values create larger bubbles. |
| adhoc_filters | array | No | [] | Array of adhoc filter objects to filter the data |
| orderby | array | No | [] | Array of columns or metrics to sort by |
| order_desc | boolean | No | true | Sort descending if true, ascending if false. Only visible when orderby is set. |
| row_limit | integer | No | 10000 | Maximum number of rows to retrieve from the datasource |
| color_scheme | string | No | (default scheme) | Color scheme name for coloring the series |
| max_bubble_size | string/number | No | "25" | Maximum size of bubbles in pixels. Can be "5", "10", "15", "25", "50", "75", "100" or custom value. |
| tooltipSizeFormat | string | No | (default format) | D3 number format string for bubble size values in tooltip |
| opacity | number | No | 0.6 | Bubble opacity from 0 (transparent) to 1 (opaque), in increments of 0.1 |
| show_legend | boolean | No | true | Whether to display the legend |
| legendType | string | No | "scroll" | Legend type: "scroll" or "plain" |
| legendOrientation | string | No | "top" | Legend position: "top", "bottom", "left", or "right" |
| legendMargin | integer | No | null | Additional padding for legend in pixels |
| legendSort | string | No | null | Sort legend: "asc" (label ascending), "desc" (label descending), or null (sort by data) |
| x_axis_label | string | No | "" | Title text for the X-axis |
| xAxisLabelRotation | number | No | 0 | Rotation angle for X-axis labels in degrees (e.g., 0, 45, 90) |
| xAxisLabelInterval | string | No | "auto" | X-axis label interval: "auto" or "0" (show all) |
| x_axis_title_margin | number | No | 15 | Margin for X-axis title in pixels. Options: 0, 15, 30, 50, 75, 100, 125, 150, 200 |
| xAxisFormat | string | No | (default format) | D3 format string for X-axis values |
| logXAxis | boolean | No | false | Use logarithmic scale for X-axis |
| y_axis_label | string | No | "" | Title text for the Y-axis |
| yAxisLabelRotation | number | No | 0 | Rotation angle for Y-axis labels in degrees (0 or 45) |
| y_axis_title_margin | number | No | 15 | Margin for Y-axis title in pixels. Options: 0, 15, 30, 50, 75, 100, 125, 150, 200 |
| y_axis_format | string | No | (default format) | D3 format string for Y-axis values |
| logYAxis | boolean | No | false | Use logarithmic scale for Y-axis |
| truncateXAxis | boolean | No | false | Truncate X-axis. Can be overridden by xAxisBounds. Only applicable for numerical X-axis. |
| xAxisBounds | array | No | [null, null] | Bounds for numerical X-axis as [min, max]. Dynamically defined if empty. Only expands range, doesn't narrow it. Only visible when truncateXAxis is true. |
| truncateYAxis | boolean | No | false | Truncate Y-axis. Can be overridden by y_axis_bounds. |
| y_axis_bounds | array | No | [null, null] | Bounds for Y-axis as [min, max]. Dynamically defined if empty. Only expands range, doesn't narrow it. Only visible when truncateYAxis is true. |

### Example Request
```json
{
  "slice_name": "Product Sales Analysis",
  "viz_type": "bubble_v2",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"entity\":\"product_name\",\"series\":\"category\",\"x\":{\"expressionType\":\"SIMPLE\",\"column\":{\"column_name\":\"price\",\"type\":\"DOUBLE\"},\"aggregate\":\"AVG\",\"label\":\"Average Price\"},\"y\":{\"expressionType\":\"SIMPLE\",\"column\":{\"column_name\":\"sales_volume\",\"type\":\"BIGINT\"},\"aggregate\":\"SUM\",\"label\":\"Total Sales\"},\"size\":{\"expressionType\":\"SIMPLE\",\"column\":{\"column_name\":\"profit_margin\",\"type\":\"DOUBLE\"},\"aggregate\":\"AVG\",\"label\":\"Average Profit Margin\"},\"row_limit\":100,\"color_scheme\":\"supersetColors\",\"max_bubble_size\":\"50\",\"opacity\":0.7,\"show_legend\":true,\"legendType\":\"scroll\",\"legendOrientation\":\"top\",\"x_axis_label\":\"Average Price ($)\",\"y_axis_label\":\"Total Sales Volume\",\"xAxisFormat\":\"$,.2f\",\"y_axis_format\":\",d\",\"tooltipSizeFormat\":\".2%\",\"adhoc_filters\":[]}",
  "description": "Analysis of product sales by price and volume with profit margin as bubble size",
  "owners": [1]
}
```

## Response Format
On success, the API returns a 201 Created status with a JSON object containing the created chart's details, including its ID and all configured parameters.

## Notes
- The `entity` field is required and defines what each bubble represents
- The `x` and `y` fields are required and must be metric objects (not simple column references)
- The `size` field is optional but recommended to take full advantage of the bubble chart's three-dimensional visualization
- Metric objects must include `expressionType`, `column`, `aggregate`, and `label` fields
- Use logarithmic scales (`logXAxis`, `logYAxis`) when dealing with data that spans multiple orders of magnitude
- Adjust `opacity` to prevent overlapping bubbles from obscuring each other
- The `max_bubble_size` controls the visual scale of bubbles - larger values make differences more apparent
- Axis bounds only expand the range and won't narrow the data extent
- D3 format strings for axes and tooltips follow the [D3 format specification](https://github.com/d3/d3-format)
