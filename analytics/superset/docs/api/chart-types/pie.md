# Pie Chart (`pie`)

## Description

The Pie Chart visualization displays data as proportional slices of a circular chart, making it ideal for showing how parts contribute to a whole. Built on Apache ECharts, it supports standard pie charts, donut charts, and Nightingale (rose) charts with extensive customization options for labels, legends, and visual appearance.

The classic visualization for showing proportional data. Great for showing how much of a company each investor gets, what demographics follow your blog, or what portion of the budget goes to the military industrial complex.

**Note:** Pie charts can be difficult to interpret precisely. If clarity of relative proportion is important, consider using a bar or other chart type instead.

## When to Use

Use a Pie Chart when you need to:
- Show proportional relationships between categories
- Display percentage breakdowns of a total
- Visualize categorical data with a limited number of segments (typically 5-10)
- Compare parts of a whole at a single point in time
- Create engaging visualizations for presentations or dashboards

## Example Use Cases

- **Financial Analysis**: Visualize budget allocation across departments or spending categories
- **Market Share**: Display competitor distribution in a market segment
- **Demographics**: Show population distribution by age groups, regions, or categories
- **Survey Results**: Present multiple-choice question responses as percentages
- **Resource Allocation**: Illustrate time or resource distribution across projects
- **Portfolio Composition**: Display investment allocation across asset classes

## Common Fields

These fields are common to all chart types in the Superset API:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `slice_name` | string | Yes | The name of the chart (1-250 characters) |
| `viz_type` | string | Yes | Must be set to `"pie"` for pie charts |
| `datasource_id` | integer | Yes | The ID of the dataset/datasource this chart will use |
| `datasource_type` | string | Yes | The type of datasource, either `"table"` or `"query"` |
| `description` | string | No | A description of the chart's purpose |
| `params` | string (JSON) | No | JSON string containing chart configuration (see params Object below) |
| `query_context` | string (JSON) | No | JSON string representing the queries needed to generate the visualization data |
| `query_context_generation` | boolean | No | Whether the query_context is user-generated to preserve user modifications |
| `cache_timeout` | integer | No | Duration in seconds for caching timeout (defaults to datasource timeout) |
| `owners` | array[integer] | No | User IDs allowed to delete or change this chart (defaults to creator) |

## params Object

The `params` field contains the chart-specific configuration as a JSON string. For pie charts, the following fields are available:

### Query Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `groupby` | array[string] | `[]` | Dimensions/columns to group by (categories for pie slices). Each element is a column name used to categorize data |
| `metric` | string or object | required | The metric to aggregate and display. Can be a simple column name or an adhoc metric object with aggregation function |
| `adhoc_filters` | array[object] | `[]` | Array of filter objects to apply to the data before visualization |
| `row_limit` | integer | `100` | Maximum number of slices to display (limits query results) |
| `sort_by_metric` | boolean | `true` | Whether to sort results by the selected metric in descending order |

### Chart Appearance

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `color_scheme` | string | varies | Color scheme for rendering the chart. Choose from available categorical color schemes |
| `show_labels_threshold` | number | `5` | Minimum threshold in percentage points for showing labels (hides labels on slices below this percentage) |
| `threshold_for_other` | number | `0` | Values less than this percentage will be grouped into an "Other" category (0 disables grouping) |
| `roseType` | string or null | `null` | Nightingale chart type: `"area"` (area-based), `"radius"` (radius-based), or `null` (standard pie) |

### Labels Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `show_labels` | boolean | `true` | Whether to display labels on the chart |
| `label_type` | string | `"key"` | What to show on labels: `"key"` (category name), `"value"`, `"percent"`, `"key_value"`, `"key_percent"`, `"key_value_percent"`, `"value_percent"`, or `"template"` (custom) |
| `label_template` | string | `null` | Custom label template when `label_type` is `"template"`. Use variables: `{name}`, `{value}`, `{percent}`. Also supports ECharts variables: `{a}` (series), `{b}` (name), `{c}` (value), `{d}` (percentage). Use `\n` for new lines |
| `labels_outside` | boolean | `true` | Whether to place labels outside the pie slices |
| `label_line` | boolean | `false` | Whether to draw lines connecting labels to pie slices when labels are outside |
| `number_format` | string | `"SMART_NUMBER"` | D3 format string for formatting numeric values in labels |
| `date_format` | string | `"smart_date"` | Date format string for temporal data in labels |
| `currency_format` | object | N/A | Currency formatting configuration with symbol and position |

### Pie Shape Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `outerRadius` | integer | `70` | Outer edge radius of the pie chart (10-100, represents percentage of container) |
| `donut` | boolean | `false` | Whether to display as a donut chart (with center hole) instead of a solid pie |
| `innerRadius` | integer | `30` | Inner radius of the donut hole (0-100, only applies when `donut` is `true`) |
| `show_total` | boolean | `false` | Whether to display the aggregate count/total in the center (useful for donut charts) |

### Legend Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `show_legend` | boolean | `true` | Whether to display a legend for the chart |
| `legendType` | string | `"scroll"` | Legend type: `"scroll"` (scrollable) or `"plain"` (static list) |
| `legendOrientation` | string | `"top"` | Legend position: `"top"`, `"bottom"`, `"left"`, or `"right"` |
| `legendMargin` | integer | varies | Additional padding/margin for the legend in pixels |
| `legendSort` | string or null | `null` | How to sort legend items: `"asc"` (label ascending), `"desc"` (label descending), or `null` (sort by data) |

## Example Request

### Basic Pie Chart

```json
{
  "slice_name": "Sales by Region",
  "viz_type": "pie",
  "datasource_id": 1,
  "datasource_type": "table",
  "description": "Distribution of sales across different regions",
  "params": "{\"groupby\": [\"region\"], \"metric\": \"sum__sales\", \"color_scheme\": \"supersetColors\", \"show_labels\": true, \"label_type\": \"key_percent\", \"row_limit\": 100}"
}
```

### Donut Chart with Custom Labels

```json
{
  "slice_name": "Budget Allocation by Department",
  "viz_type": "pie",
  "datasource_id": 2,
  "datasource_type": "table",
  "description": "Annual budget distribution across departments with total displayed in center",
  "params": "{\"groupby\": [\"department\"], \"metric\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"budget_amount\"}, \"aggregate\": \"SUM\", \"label\": \"Total Budget\"}, \"donut\": true, \"innerRadius\": 40, \"outerRadius\": 75, \"show_total\": true, \"show_labels\": true, \"label_type\": \"template\", \"label_template\": \"{name}\\n${value}\", \"labels_outside\": true, \"label_line\": true, \"number_format\": \"$,.2f\", \"color_scheme\": \"bnbColors\", \"sort_by_metric\": true, \"row_limit\": 50, \"show_labels_threshold\": 3, \"legendOrientation\": \"right\", \"legendType\": \"scroll\"}"
}
```

### Nightingale Chart (Rose)

```json
{
  "slice_name": "Product Category Performance",
  "viz_type": "pie",
  "datasource_id": 3,
  "datasource_type": "table",
  "description": "Product sales comparison using Nightingale chart visualization",
  "params": "{\"groupby\": [\"product_category\"], \"metric\": \"sum__quantity_sold\", \"roseType\": \"radius\", \"show_labels\": true, \"label_type\": \"key_value\", \"labels_outside\": false, \"color_scheme\": \"lyftColors\", \"outerRadius\": 80, \"show_legend\": true, \"legendOrientation\": \"bottom\", \"number_format\": \",.0f\", \"sort_by_metric\": true}"
}
```

### Pie Chart with Filters and Grouping

```json
{
  "slice_name": "Customer Segmentation",
  "viz_type": "pie",
  "datasource_id": 4,
  "datasource_type": "table",
  "description": "Customer distribution by age group for active customers only",
  "params": "{\"groupby\": [\"age_group\"], \"metric\": \"count\", \"adhoc_filters\": [{\"expressionType\": \"SIMPLE\", \"subject\": \"status\", \"operator\": \"==\", \"comparator\": \"active\", \"clause\": \"WHERE\"}], \"row_limit\": 100, \"threshold_for_other\": 2, \"show_labels\": true, \"label_type\": \"key_value_percent\", \"labels_outside\": true, \"label_line\": true, \"show_labels_threshold\": 1, \"color_scheme\": \"googleCategory20c\", \"legendOrientation\": \"top\", \"sort_by_metric\": true}"
}
```

## Notes

- The `params` field must be a valid JSON string. When constructing the request, serialize your params object to a JSON string.
- For `metric`, you can use either:
  - A simple string representing a column name with a default aggregation (e.g., `"sum__sales"`)
  - An adhoc metric object with fields: `expressionType`, `column`, `aggregate`, and `label`
- The `adhoc_filters` array can contain filter objects with fields: `expressionType`, `subject`, `operator`, `comparator`, and `clause`
- Use `threshold_for_other` to automatically group small slices into an "Other" category, improving readability for charts with many categories
- The `show_labels_threshold` helps prevent label overlap by hiding labels on small slices
- When `donut` is `true`, you can use `show_total` to display aggregate metrics in the center of the donut
- Nightingale charts (`roseType`: `"area"` or `"radius"`) are useful for comparing values where the differences are subtle, as they use both angle and radius to represent data
- Available color schemes depend on your Superset configuration. Common schemes include: `"supersetColors"`, `"bnbColors"`, `"lyftColors"`, `"googleCategory10c"`, `"googleCategory20c"`, etc.
- For numeric formatting, use D3 format strings (e.g., `",.2f"` for comma-separated with 2 decimals, `"$,.0f"` for currency)

## API Endpoint

To create a pie chart, send a POST request to:

```
POST /api/v1/chart/
```

Include the JSON payload with the fields described above. Ensure you have appropriate authentication headers and permissions to create charts in your Superset instance.

## Related Resources

- [Apache ECharts Pie Chart Documentation](https://echarts.apache.org/en/option.html#series-pie)
- [Superset Charts API](../charts.md)
- [D3 Number Formatting Reference](https://d3js.org/d3-format)
- [D3 Time Formatting Reference](https://d3js.org/d3-time-format)
