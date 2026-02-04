# Sunburst Chart (`sunburst_v2`)

## Description

The Sunburst Chart visualization uses concentric circles to visualize hierarchical data and the flow of data through different stages of a system. Built on Apache ECharts, it displays multi-level categorical relationships where each ring represents a level in the hierarchy, with the innermost circle representing the top of the hierarchy.

Hover over individual paths in the visualization to understand the stages a value took. This chart type is particularly useful for multi-stage, multi-group visualizing funnels and pipelines, allowing you to see both the hierarchical structure and proportional relationships simultaneously.

## When to Use

Use a Sunburst Chart when you need to:
- Visualize hierarchical data with multiple levels
- Show proportional relationships within a hierarchy
- Display data flow through different stages of a system
- Represent multi-level categorical breakdowns
- Analyze funnel or pipeline data with multiple stages and groups
- Compare both hierarchy and magnitude simultaneously

## Example Use Cases

- **Sales Hierarchies**: Visualize sales data broken down by region > country > product category > product
- **Website Analytics**: Show user journey through website sections > pages > actions with conversion metrics
- **Organizational Structure**: Display company hierarchy with headcount or budget at each level
- **File System Analysis**: Illustrate directory structure with file sizes
- **Process Funnels**: Analyze multi-stage conversion funnels with group segmentation
- **Budget Breakdown**: Show budget allocation from department > team > project > expense category
- **Product Taxonomy**: Display product categories > subcategories > items with sales volumes

## Common Fields

These fields are common to all chart types in the Superset API:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `slice_name` | string | Yes | The name of the chart (1-250 characters) |
| `viz_type` | string | Yes | Must be set to `"sunburst_v2"` for sunburst charts |
| `datasource_id` | integer | Yes | The ID of the dataset/datasource this chart will use |
| `datasource_type` | string | Yes | The type of datasource, either `"table"` or `"query"` |
| `description` | string | No | A description of the chart's purpose |
| `params` | string (JSON) | No | JSON string containing chart configuration (see params Object below) |
| `query_context` | string (JSON) | No | JSON string representing the queries needed to generate the visualization data |
| `query_context_generation` | boolean | No | Whether the query_context is user-generated to preserve user modifications |
| `cache_timeout` | integer | No | Duration in seconds for caching timeout (defaults to datasource timeout) |
| `owners` | array[integer] | No | User IDs allowed to delete or change this chart (defaults to creator) |

## params Object

The `params` field contains the chart-specific configuration as a JSON string. For sunburst charts, the following fields are available:

### Query Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `columns` | array[string] | `[]` | Hierarchy levels for the chart. Each level is represented by one ring with the innermost circle as the top of the hierarchy. Order matters: first column is the innermost ring |
| `metric` | string or object | required | Primary metric used to define the arc segment sizes. Can be a simple column name or an adhoc metric object |
| `secondary_metric` | string or object | `null` | Optional secondary metric used to define color as a ratio against the primary metric. When omitted, color is categorical and based on labels |
| `adhoc_filters` | array[object] | `[]` | Array of filter objects to apply to the data before visualization |
| `row_limit` | integer | `10000` | Maximum number of rows to fetch from the data source |
| `sort_by_metric` | boolean | `false` | Whether to sort results by the selected metric in descending order |

### Chart Appearance

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `color_scheme` | string | varies | Categorical color scheme for rendering the chart. Used when only a primary metric is provided or when secondary metric equals primary metric |
| `linear_color_scheme` | string | varies | Linear color scheme for rendering the chart. Used when a secondary metric is provided that differs from the primary metric |

### Labels Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `show_labels` | boolean | `false` | Whether to display labels on the chart segments |
| `show_labels_threshold` | number | `5` | Minimum threshold in percentage points for showing labels. Labels on segments below this percentage will be hidden |
| `show_total` | boolean | `false` | Whether to display the aggregate count in the center of the chart |
| `label_type` | string | `"key"` | What to show on labels: `"key"` (category name), `"value"` (numeric value), or `"key_value"` (both category and value) |
| `number_format` | string | `"SMART_NUMBER"` | D3 format string for formatting numeric values in labels and tooltips |
| `date_format` | string | `"smart_date"` | Date format string for temporal data in labels |
| `currency_format` | object | N/A | Currency formatting configuration with symbol and position. Formats metrics or columns with currency symbols as prefixes or suffixes |

## Example Request

### Basic Sunburst Chart

```json
{
  "slice_name": "Sales Hierarchy by Region and Category",
  "viz_type": "sunburst_v2",
  "datasource_id": 1,
  "datasource_type": "table",
  "description": "Hierarchical view of sales broken down by region, country, and product category",
  "params": "{\"columns\": [\"region\", \"country\", \"category\"], \"metric\": \"sum__sales\", \"color_scheme\": \"supersetColors\", \"show_labels\": true, \"label_type\": \"key\", \"show_labels_threshold\": 5, \"row_limit\": 10000}"
}
```

### Sunburst with Secondary Metric (Ratio Coloring)

```json
{
  "slice_name": "Revenue vs. Profit Margin",
  "viz_type": "sunburst_v2",
  "datasource_id": 2,
  "datasource_type": "table",
  "description": "Product hierarchy showing revenue (size) and profit margin (color intensity)",
  "params": "{\"columns\": [\"department\", \"category\", \"product\"], \"metric\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"revenue\"}, \"aggregate\": \"SUM\", \"label\": \"Total Revenue\"}, \"secondary_metric\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"profit\"}, \"aggregate\": \"SUM\", \"label\": \"Total Profit\"}, \"linear_color_scheme\": \"blue_white_yellow\", \"show_labels\": true, \"label_type\": \"key_value\", \"number_format\": \"$,.0f\", \"show_labels_threshold\": 3, \"row_limit\": 5000}"
}
```

### Website Analytics Funnel

```json
{
  "slice_name": "User Journey Conversion Funnel",
  "viz_type": "sunburst_v2",
  "datasource_id": 3,
  "datasource_type": "table",
  "description": "Multi-stage user journey showing page sections, pages, and actions with user counts",
  "params": "{\"columns\": [\"section\", \"page\", \"action\"], \"metric\": \"count_distinct__user_id\", \"color_scheme\": \"lyftColors\", \"show_labels\": true, \"label_type\": \"key_value\", \"show_labels_threshold\": 2, \"show_total\": true, \"number_format\": \",.0f\", \"sort_by_metric\": true, \"row_limit\": 10000}"
}
```

### Sunburst with Filters and Custom Formatting

```json
{
  "slice_name": "Active Customer Spending Hierarchy",
  "viz_type": "sunburst_v2",
  "datasource_id": 4,
  "datasource_type": "table",
  "description": "Customer segment breakdown by tier, industry, and company for active customers",
  "params": "{\"columns\": [\"customer_tier\", \"industry\", \"company\"], \"metric\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"annual_spending\"}, \"aggregate\": \"SUM\", \"label\": \"Annual Spending\"}, \"adhoc_filters\": [{\"expressionType\": \"SIMPLE\", \"subject\": \"status\", \"operator\": \"==\", \"comparator\": \"active\", \"clause\": \"WHERE\"}], \"color_scheme\": \"bnbColors\", \"show_labels\": true, \"label_type\": \"key_value\", \"number_format\": \"$,.2s\", \"show_labels_threshold\": 3, \"currency_format\": {\"symbol\": \"USD\", \"symbolPosition\": \"prefix\"}, \"sort_by_metric\": true, \"row_limit\": 10000}"
}
```

### Multi-Level Budget Breakdown

```json
{
  "slice_name": "Budget Allocation Breakdown",
  "viz_type": "sunburst_v2",
  "datasource_id": 5,
  "datasource_type": "table",
  "description": "Four-level budget hierarchy from division to specific expense items",
  "params": "{\"columns\": [\"division\", \"department\", \"project\", \"expense_category\"], \"metric\": \"sum__allocated_budget\", \"color_scheme\": \"googleCategory20c\", \"show_labels\": true, \"label_type\": \"key\", \"show_labels_threshold\": 4, \"show_total\": true, \"number_format\": \"$,.0f\", \"row_limit\": 15000}"
}
```

## Notes

- The `params` field must be a valid JSON string. When constructing the request, serialize your params object to a JSON string.
- The `columns` array defines the hierarchy structure. Order is important: the first column becomes the innermost ring (top of hierarchy), and subsequent columns form outer rings.
- For `metric` and `secondary_metric`, you can use either:
  - A simple string representing a column name with a default aggregation (e.g., `"sum__sales"`)
  - An adhoc metric object with fields: `expressionType`, `column`, `aggregate`, and `label`
- The `adhoc_filters` array can contain filter objects with fields: `expressionType`, `subject`, `operator`, `comparator`, and `clause`
- When a `secondary_metric` is provided and differs from the primary metric, the chart uses a linear color scale to represent the ratio between the two metrics. The arc segment size is still determined by the primary metric.
- When no `secondary_metric` is provided (or it equals the primary metric), the chart uses a categorical color scheme based on the category labels.
- The `show_labels_threshold` helps prevent label overlap by hiding labels on segments that represent less than the specified percentage of their parent.
- Use `show_total` to display the aggregate value in the center of the chart, which is particularly useful for understanding the total magnitude.
- The sunburst chart supports interactive drill-down: clicking on a segment will zoom into that portion of the hierarchy.
- Available color schemes depend on your Superset configuration. Common schemes include:
  - Categorical: `"supersetColors"`, `"bnbColors"`, `"lyftColors"`, `"googleCategory10c"`, `"googleCategory20c"`, etc.
  - Linear: `"blue_white_yellow"`, `"fire"`, `"white_black"`, `"black_white"`, etc.
- For numeric formatting, use D3 format strings:
  - `",.0f"` - comma-separated with no decimals
  - `"$,.2f"` - currency with 2 decimals
  - `",.2s"` - SI prefix notation (K, M, B)
  - `".1%"` - percentage with 1 decimal
- The chart supports drill-to-detail and drill-by behaviors for interactive data exploration.

## API Endpoint

To create a sunburst chart, send a POST request to:

```
POST /api/v1/chart/
```

Include the JSON payload with the fields described above. Ensure you have appropriate authentication headers and permissions to create charts in your Superset instance.

## Related Resources

- [Apache ECharts Sunburst Documentation](https://echarts.apache.org/en/option.html#series-sunburst)
- [Superset Charts API](../charts.md)
- [D3 Number Formatting Reference](https://d3js.org/d3-format)
- [D3 Time Formatting Reference](https://d3js.org/d3-time-format)
