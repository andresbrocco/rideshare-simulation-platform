# Treemap (treemap_v2)

## Description

The Treemap visualization displays hierarchical relationships of data using nested rectangles, where the area of each rectangle represents a quantitative value. This chart type is ideal for showing proportion and contribution to the whole across multiple levels of categorical data. Treemaps are built using Apache ECharts and support interactive features like drill-down and drill-to-detail operations.

## When to Use

Use a Treemap when you need to:
- Visualize hierarchical data with multiple levels of grouping
- Show proportional relationships where size represents magnitude
- Compare relative sizes of categories and subcategories at a glance
- Identify patterns in nested categorical data
- Display part-to-whole relationships with hierarchical structure
- Present complex data structures in a space-efficient manner

## Example Use Cases

- **Sales Analysis**: Display product sales broken down by category > subcategory > individual products
- **Budget Allocation**: Show organizational budget distribution across departments > teams > expense categories
- **Website Analytics**: Visualize page views by section > page type > individual pages
- **Inventory Management**: Display stock levels organized by warehouse > product category > specific items
- **Market Share Analysis**: Show market share distribution by region > company > product line
- **Resource Utilization**: Visualize compute resource usage by service > instance type > individual instances

## Common Fields

The following fields are common to all chart types. For details on their structure and usage, see the [Charts API documentation](/docs/api/README.md).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `slice_name` | string | Yes | The name/title of the chart (max 250 characters) |
| `description` | string | No | A description of the chart's purpose |
| `viz_type` | string | Yes | Must be `"treemap_v2"` for this chart type |
| `datasource_id` | integer | Yes | The ID of the dataset/datasource this chart uses |
| `datasource_type` | string | Yes | The type of datasource (e.g., `"table"`, `"dataset"`) |
| `params` | string | No | JSON string containing chart-specific parameters (see params Object below) |
| `query_context` | string | No | JSON string representing the query configuration |
| `cache_timeout` | integer | No | Duration in seconds for caching this chart's data |
| `owners` | array[integer] | No | List of user IDs who own this chart |
| `dashboards` | array[integer] | No | List of dashboard IDs to include this chart in |
| `certified_by` | string | No | Person or group that has certified this chart |
| `certification_details` | string | No | Details about the certification |

## params Object

The `params` field should be a JSON string containing an object with the following treemap-specific configuration options:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `groupby` | array | Yes | `[]` | Array of column names or objects defining the hierarchical grouping. Multiple columns create nested hierarchy levels. |
| `metric` | string \| object | Yes | - | The metric to aggregate and use for sizing rectangles. Can be a column name (string) or an adhoc metric object. |
| `row_limit` | integer | No | `10000` | Maximum number of rows to retrieve from the datasource. Must be >= 0. |
| `sort_by_metric` | boolean | No | `false` | Whether to sort results by the selected metric in descending order. |
| `adhoc_filters` | array | No | `[]` | Array of filter objects to apply to the query. Each filter specifies conditions on columns. |
| `color_scheme` | string | No | (default scheme) | The color scheme to use for rendering the treemap rectangles. |
| `show_labels` | boolean | No | `true` | Whether to display labels on the treemap rectangles. |
| `show_upper_labels` | boolean | No | `true` | Whether to show labels on parent nodes (nodes with children). |
| `label_type` | string | No | `"key_value"` | What to display on labels. Options: `"key"` (category name only), `"value"` (metric value only), `"key_value"` (both category and value). |
| `number_format` | string | No | `"SMART_NUMBER"` | D3 format string for formatting numeric values in labels. |
| `date_format` | string | No | `"smart_date"` | D3 time format string for formatting date values if present. |
| `currency_format` | object | No | - | Currency formatting configuration with symbol, prefix/suffix position, and format options. |

### groupby Structure

The `groupby` field defines the hierarchical structure of the treemap. Each element can be:

**Simple column reference (string)**:
```json
"groupby": ["category", "subcategory"]
```

**Column object**:
```json
"groupby": [
  {
    "column_name": "category",
    "type": "VARCHAR"
  }
]
```

### metric Structure

The `metric` field defines the value used to size each rectangle. It can be:

**Simple metric reference (string)**:
```json
"metric": "sales_amount"
```

**Adhoc metric (object)** for custom aggregations:
```json
"metric": {
  "expressionType": "SIMPLE",
  "aggregate": "SUM",
  "column": {
    "column_name": "revenue",
    "type": "BIGINT"
  },
  "label": "Total Revenue"
}
```

**SQL metric (object)** for complex calculations:
```json
"metric": {
  "expressionType": "SQL",
  "sqlExpression": "SUM(price * quantity)",
  "label": "Total Sales"
}
```

### adhoc_filters Structure

Each filter object in the `adhoc_filters` array has the following structure:

```json
{
  "col": "country",
  "op": "IN",
  "val": ["USA", "Canada", "Mexico"]
}
```

Supported operators include: `"IN"`, `"NOT IN"`, `"=="`, `"!="`, `">"`, `">="`, `"<"`, `"<="`, `"LIKE"`, `"IS NULL"`, `"IS NOT NULL"`, and others.

### currency_format Structure

```json
{
  "symbol": "USD",
  "symbolPosition": "prefix"
}
```

Or use auto-detection:
```json
{
  "symbol": "AUTO"
}
```

## Example Request JSON

### Basic Treemap

Create a simple treemap showing sales by product category and subcategory:

```json
{
  "slice_name": "Sales by Category Treemap",
  "description": "Hierarchical view of sales broken down by category and subcategory",
  "viz_type": "treemap_v2",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{
    \"groupby\": [\"category\", \"subcategory\"],
    \"metric\": \"sales_total\",
    \"row_limit\": 1000,
    \"sort_by_metric\": true,
    \"color_scheme\": \"supersetColors\",
    \"show_labels\": true,
    \"show_upper_labels\": true,
    \"label_type\": \"key_value\",
    \"number_format\": \"$,.2f\",
    \"adhoc_filters\": [
      {
        \"col\": \"year\",
        \"op\": \"==\",
        \"val\": 2024
      }
    ]
  }",
  "cache_timeout": 3600
}
```

### Treemap with Adhoc Metric

Create a treemap with a custom calculated metric:

```json
{
  "slice_name": "Profit Margin by Region",
  "description": "Profit margins visualized hierarchically by region and country",
  "viz_type": "treemap_v2",
  "datasource_id": 5,
  "datasource_type": "table",
  "params": "{
    \"groupby\": [\"region\", \"country\"],
    \"metric\": {
      \"expressionType\": \"SQL\",
      \"sqlExpression\": \"SUM(profit) / SUM(revenue) * 100\",
      \"label\": \"Profit Margin %\",
      \"hasCustomLabel\": true
    },
    \"row_limit\": 500,
    \"sort_by_metric\": true,
    \"color_scheme\": \"bnbColors\",
    \"show_labels\": true,
    \"show_upper_labels\": true,
    \"label_type\": \"key_value\",
    \"number_format\": \".2f\",
    \"adhoc_filters\": [
      {
        \"col\": \"status\",
        \"op\": \"==\",
        \"val\": \"active\"
      }
    ]
  }"
}
```

### Treemap with Multiple Hierarchical Levels

Create a treemap with three levels of hierarchy and value-only labels:

```json
{
  "slice_name": "Website Traffic Breakdown",
  "description": "Page views organized by section, page type, and individual page",
  "viz_type": "treemap_v2",
  "datasource_id": 12,
  "datasource_type": "table",
  "params": "{
    \"groupby\": [\"section\", \"page_type\", \"page_name\"],
    \"metric\": {
      \"expressionType\": \"SIMPLE\",
      \"aggregate\": \"SUM\",
      \"column\": {
        \"column_name\": \"page_views\",
        \"type\": \"BIGINT\"
      },
      \"label\": \"Total Page Views\"
    },
    \"row_limit\": 5000,
    \"sort_by_metric\": true,
    \"color_scheme\": \"googleCategory20c\",
    \"show_labels\": true,
    \"show_upper_labels\": false,
    \"label_type\": \"value\",
    \"number_format\": \"SMART_NUMBER\",
    \"adhoc_filters\": [
      {
        \"col\": \"date\",
        \"op\": \">=\",
        \"val\": \"2024-01-01\"
      },
      {
        \"col\": \"is_bot\",
        \"op\": \"==\",
        \"val\": false
      }
    ]
  }",
  "dashboards": [7],
  "owners": [10]
}
```

### Treemap with Currency Formatting

Create a treemap with automatic currency detection:

```json
{
  "slice_name": "Revenue by Product Line",
  "description": "Product revenue with automatic currency formatting",
  "viz_type": "treemap_v2",
  "datasource_id": 8,
  "datasource_type": "table",
  "params": "{
    \"groupby\": [\"product_line\", \"product_name\"],
    \"metric\": \"revenue\",
    \"row_limit\": 2000,
    \"sort_by_metric\": true,
    \"color_scheme\": \"d3Category20\",
    \"show_labels\": true,
    \"show_upper_labels\": true,
    \"label_type\": \"key_value\",
    \"number_format\": \",.0f\",
    \"currency_format\": {
      \"symbol\": \"AUTO\",
      \"symbolPosition\": \"prefix\"
    }
  }"
}
```

## Notes

- The treemap supports interactive drill-down and drill-to-detail behaviors
- Multiple hierarchy levels are created by adding more columns to the `groupby` array
- The `label_type` setting controls what information is displayed on each rectangle
- When `show_upper_labels` is false, only leaf nodes (rectangles without children) show labels
- The chart uses Apache ECharts for rendering, providing smooth animations and interactions
- Color schemes are applied automatically across the hierarchy to differentiate categories
- The `SMART_NUMBER` format automatically adjusts number formatting based on magnitude (K, M, B suffixes)
- The `smart_date` format automatically chooses appropriate date formatting based on the time range
