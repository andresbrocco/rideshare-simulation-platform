# Bubble Chart (Legacy) (`bubble`)

## Description
The Bubble Chart visualizes data across three quantitative dimensions simultaneously using the X-axis position, Y-axis position, and bubble size. Bubbles can be grouped by a categorical dimension (series) with each series represented by a distinct color, enabling comparison of multiple groups across three numeric metrics in a single visualization. **Note**: this chart type is marked as **deprecated** and uses the legacy NVD3 library.

## When to Use
Use this chart type when you need to analyze relationships between three continuous variables and optionally compare different categories. It is particularly effective for identifying correlations, patterns, and outliers across multiple dimensions, such as comparing market segments by revenue, growth rate, and market size.

## Example Use Cases
- Analyzing product performance by sales volume (X), profit margin (Y), and market share (bubble size) across different product categories (series)
- Comparing countries by GDP per capita (X), life expectancy (Y), and population (bubble size) across continents
- Evaluating marketing campaigns by cost (X), conversions (Y), and reach (bubble size) across different channels
- Visualizing employee performance by experience (X), productivity (Y), and project count (bubble size) across departments
- Studying competitor analysis by price point (X), customer satisfaction (Y), and market share (bubble size)

## Request Format

### Common Fields
| Field                 | Type    | Required | Description                                      |
| --------------------- | ------- | -------- | ------------------------------------------------ |
| slice_name            | string  | Yes      | Chart name (max 250 chars)                       |
| viz_type              | string  | Yes      | Must be `bubble`                                 |
| datasource_id         | integer | Yes      | ID of the datasource                             |
| datasource_type       | string  | Yes      | Type of datasource (e.g., 'table')               |
| params                | string  | Yes      | JSON string containing chart-specific parameters |
| description           | string  | No       | Chart description                                |
| owners                | array   | No       | List of owner user IDs                           |
| cache_timeout         | integer | No       | Cache timeout in seconds                         |
| dashboards            | array   | No       | List of dashboard IDs to add chart to            |
| certified_by          | string  | No       | Name of certifier                                |
| certification_details | string  | No       | Certification details                            |

### params Object
The `params` field must be a JSON-encoded string containing the following chart-specific parameters:

| Field             | Type           | Required | Default          | Description                                                                                                                                                                 |
| ----------------- | -------------- | -------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| series            | string         | No       | null             | Dimension column that defines grouping of entities. Each series is represented by a specific color in the chart.                                                            |
| entity            | string         | Yes      | null             | The element to be plotted on the chart. Each distinct value becomes a separate bubble.                                                                                      |
| x                 | object/string  | Yes      | null             | Metric or column that returns the values for the chart's x-axis position.                                                                                                   |
| y                 | object/string  | Yes      | null             | Metric or column that returns the values for the chart's y-axis position.                                                                                                   |
| size              | object/string  | No       | null             | Metric used to calculate bubble size. If not specified, all bubbles will have the same size.                                                                                |
| adhoc_filters     | array          | No       | []               | List of adhoc filters to apply to the data. Each filter is an object with properties like clause, subject, operator, comparator, and expressionType.                        |
| max_bubble_size   | string         | No       | '25'             | Maximum size of bubbles in pixels. Valid options: '5', '10', '15', '25', '50', '75', '100', or custom value.                                                                |
| limit             | integer        | No       | null             | Series limit. Limits the number of series displayed using a subquery. Useful when grouping by high cardinality columns.                                                     |
| color_scheme      | string         | No       | 'supersetColors' | Color scheme for rendering the chart. Must be a valid color scheme name from the available schemes.                                                                         |
| show_legend       | boolean        | No       | true             | Whether to display the legend (toggles).                                                                                                                                    |
| x_axis_label      | string         | No       | ''               | Label text for the X-axis.                                                                                                                                                  |
| left_margin       | string/integer | No       | 'auto'           | Left margin in pixels, allowing more room for axis labels. Valid options: 'auto', 50, 75, 100, 125, 150, 200.                                                               |
| x_axis_format     | string         | No       | 'SMART_NUMBER'   | Format string for X-axis values. Supports D3 format options.                                                                                                                |
| x_ticks_layout    | string         | No       | 'auto'           | The way ticks are laid out on the X-axis. Valid options: 'auto', 'flat', '45°', 'staggered'.                                                                                |
| x_log_scale       | boolean        | No       | false            | Use a log scale for the X-axis.                                                                                                                                             |
| x_axis_showminmax | boolean        | No       | false            | Whether to display the min and max values of the X-axis.                                                                                                                    |
| y_axis_label      | string         | No       | ''               | Label text for the Y-axis.                                                                                                                                                  |
| bottom_margin     | string/integer | No       | 'auto'           | Bottom margin in pixels, allowing more room for axis labels. Valid options: 'auto', 50, 75, 100, 125, 150, 200.                                                             |
| y_axis_format     | string         | No       | 'SMART_NUMBER'   | Format string for Y-axis values. Supports D3 format options with documentation.                                                                                             |
| y_log_scale       | boolean        | No       | false            | Use a log scale for the Y-axis.                                                                                                                                             |
| y_axis_showminmax | boolean        | No       | false            | Whether to display the min and max values of the Y-axis.                                                                                                                    |
| y_axis_bounds     | array          | No       | [null, null]     | Bounds for the Y-axis as [min, max]. When left empty, bounds are dynamically defined based on data. This feature expands the axis range but won't narrow the data's extent. |

### Metric Object Format
Metrics (x, y, size) can be specified as either:

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
  "slice_name": "Product Performance Analysis",
  "viz_type": "bubble",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"series\": \"product_category\", \"entity\": \"product_name\", \"x\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"revenue\", \"type\": \"DOUBLE\"}, \"aggregate\": \"SUM\", \"label\": \"Total Revenue\"}, \"y\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"profit_margin\", \"type\": \"DOUBLE\"}, \"aggregate\": \"AVG\", \"label\": \"Avg Profit Margin\"}, \"size\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"units_sold\", \"type\": \"INTEGER\"}, \"aggregate\": \"SUM\", \"label\": \"Total Units Sold\"}, \"adhoc_filters\": [{\"clause\": \"WHERE\", \"subject\": \"sales_date\", \"operator\": \"TEMPORAL_RANGE\", \"comparator\": \"Last year\", \"expressionType\": \"SIMPLE\"}], \"max_bubble_size\": \"50\", \"limit\": 20, \"color_scheme\": \"supersetColors\", \"show_legend\": true, \"x_axis_label\": \"Revenue ($)\", \"y_axis_label\": \"Profit Margin (%)\", \"x_axis_format\": \"$,.2f\", \"y_axis_format\": \".1%\", \"x_log_scale\": false, \"y_log_scale\": false, \"x_axis_showminmax\": true, \"y_axis_showminmax\": true, \"y_axis_bounds\": [0, null], \"x_ticks_layout\": \"auto\", \"left_margin\": \"auto\", \"bottom_margin\": \"auto\"}",
  "description": "Bubble chart showing product performance across revenue, profit margin, and sales volume",
  "owners": [1]
}
```

## Notes
- This chart type is marked as **deprecated** and uses the legacy NVD3 library
- The `entity` field is required and determines which distinct values become individual bubbles
- All three metrics (x, y, size) should be numeric for proper visualization
- When `series` is specified, bubbles are colored by category; otherwise, all bubbles use the same color
- The `max_bubble_size` parameter controls the pixel size of the largest bubble; smaller bubbles scale proportionally
- Log scales are useful when dealing with data that spans multiple orders of magnitude
- Format strings support D3 formatting syntax for numeric and percentage displays
