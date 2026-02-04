# Handlebars (`handlebars`)

## Description
The Handlebars chart type is a highly customizable template-based visualization that allows you to render data using Handlebars templating syntax. It provides the flexibility to create custom HTML layouts with embedded data, enabling you to design unique visualizations beyond standard chart types. The chart supports custom CSS styling and includes built-in Handlebars helpers for common formatting tasks like date formatting, number formatting, and JSON manipulation.

## When to Use
Use the Handlebars chart when you need complete control over the visual presentation of your data, when standard chart types don't meet your specific layout requirements, or when you want to create custom dashboards with branded or highly stylized content. This chart is ideal for users familiar with HTML and Handlebars templating who need to create custom data presentations.

## Example Use Cases
- Custom KPI dashboards with branded layouts and specific styling requirements
- Data reports that need to match existing design systems or corporate templates
- HTML email templates populated with database query results
- Custom data cards or widgets with complex nested structures
- Interactive data lists with custom formatting and conditional styling

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `handlebars` |
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
| query_mode | string | No | 'aggregate' | Query mode for data retrieval. Valid values: 'aggregate', 'raw'. Determines whether to use aggregated metrics or raw column data. |
| handlebars_template | string | Yes | - | Handlebars template string that defines how the data should be rendered. Required field. The template receives data in a `data` array variable. |
| styleTemplate | string | No | '' | CSS styles to apply to the chart. Note: HTML sanitization must be configured to use CSS. |
| groupby | array | No | [] | Columns to group by (aggregate mode only). Array of column names or adhoc column objects. |
| all_columns | array | No | [] | Columns to display (raw mode only). Array of column names. Required when in raw mode. |
| metrics | array | No | [] | Array of metrics to compute (aggregate mode only). Can be metric names (strings) or adhoc metric objects. |
| percent_metrics | array | No | [] | Array of percentage metrics (aggregate mode only). Percentage metrics are calculated only from data within the row limit. |
| timeseries_limit_metric | object/string | No | null | Metric used for limiting and sorting series (aggregate mode only). Can be a metric name or adhoc metric object. |
| order_by_cols | array | No | [] | Columns to order results by (raw mode only). Array of column names. |
| order_desc | boolean | No | true | Whether to sort descending or ascending. Only visible when timeseries_limit_metric has a value (aggregate mode). |
| row_limit | integer | No | 10000 | Limits the number of rows that are computed in the query. |
| adhoc_filters | array | No | [] | Array of adhoc filter objects to filter the data. |
| include_time | boolean | No | false | Whether to include the time granularity as defined in the time section (aggregate mode only). |
| show_totals | boolean | No | false | Show total aggregations of selected metrics. Note that row limit does not apply to the result (aggregate mode only). |

### Handlebars Helpers
The following Handlebars helpers are available in templates:

- **dateFormat**: Formats a date using a specified format
- **stringify**: Converts an object to a JSON string
- **formatNumber**: Formats a number using locale-specific formatting
- **parseJson**: Parses a JSON string into a JavaScript object

### Example Request
```json
{
  "slice_name": "Custom Product Listing",
  "viz_type": "handlebars",
  "datasource_id": 123,
  "datasource_type": "table",
  "params": "{\"query_mode\": \"aggregate\", \"handlebars_template\": \"<div class='product-grid'>\\n  <h2>Top Products</h2>\\n  <ul class='data-list'>\\n    {{#each data}}\\n      <li class='product-item'>\\n        <h3>{{this.product_name}}</h3>\\n        <p class='sales'>Sales: {{formatNumber this.sum__sales}}</p>\\n        <p class='date'>Last Updated: {{dateFormat this.__timestamp '%Y-%m-%d'}}</p>\\n      </li>\\n    {{/each}}\\n  </ul>\\n</div>\", \"styleTemplate\": \".product-grid { padding: 20px; background-color: #f5f5f5; }\\n.data-list { list-style: none; padding: 0; }\\n.product-item { background: white; margin: 10px 0; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }\\n.product-item h3 { margin-top: 0; color: #333; }\\n.sales { font-size: 1.2em; font-weight: bold; color: #28a745; }\\n.date { color: #666; font-size: 0.9em; }\", \"groupby\": [\"product_name\"], \"metrics\": [\"sum__sales\"], \"row_limit\": 10, \"timeseries_limit_metric\": \"sum__sales\", \"order_desc\": true, \"include_time\": false, \"show_totals\": false, \"adhoc_filters\": [{\"clause\": \"WHERE\", \"comparator\": \"2023\", \"expressionType\": \"SIMPLE\", \"operator\": \"TEMPORAL_RANGE\", \"subject\": \"order_date\"}]}",
  "description": "Custom styled product listing with sales data",
  "owners": [1]
}
```

### Raw Mode Example
```json
{
  "slice_name": "Raw Customer Data List",
  "viz_type": "handlebars",
  "datasource_id": 456,
  "datasource_type": "table",
  "params": "{\"query_mode\": \"raw\", \"handlebars_template\": \"<table class='customer-table'>\\n  <thead>\\n    <tr>\\n      <th>Customer</th>\\n      <th>Email</th>\\n      <th>Status</th>\\n    </tr>\\n  </thead>\\n  <tbody>\\n    {{#each data}}\\n      <tr>\\n        <td>{{this.customer_name}}</td>\\n        <td>{{this.email}}</td>\\n        <td>{{this.status}}</td>\\n      </tr>\\n    {{/each}}\\n  </tbody>\\n</table>\", \"styleTemplate\": \".customer-table { width: 100%; border-collapse: collapse; }\\n.customer-table th, .customer-table td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }\\n.customer-table th { background-color: #4CAF50; color: white; }\", \"all_columns\": [\"customer_name\", \"email\", \"status\"], \"order_by_cols\": [\"customer_name\"], \"row_limit\": 50, \"adhoc_filters\": []}",
  "description": "Raw customer data displayed in a custom table format",
  "owners": [1]
}
```

## Notes
- The `handlebars_template` field is required and cannot be empty. The default template provides a basic list structure.
- **Query Modes**: The chart operates in two mutually exclusive modes:
  - **Aggregate Mode**: Use `groupby`, `metrics`, `percent_metrics`, and `timeseries_limit_metric`. Aggregates data based on groupings.
  - **Raw Mode**: Use `all_columns` and `order_by_cols`. Returns raw, unaggregated data. `all_columns` is required in raw mode.
- **CSS Styling**: To use the `styleTemplate` field, HTML sanitization must be properly configured in Superset. Without proper configuration, CSS styles may be stripped for security reasons.
- **Data Access**: The template receives data in the `data` variable, which is an array of objects where each object represents a row.
- **Helper Functions**: Use the built-in Handlebars helpers (`dateFormat`, `stringify`, `formatNumber`, `parseJson`) to format data within templates.
- **Template Syntax**: The template uses standard Handlebars syntax including `{{#each}}` loops, `{{this}}` references, and `{{variableName}}` interpolation.
- **Security Considerations**: Be cautious when using this chart type with untrusted data, as improperly sanitized HTML could pose security risks.
- **Validation**: In aggregate mode, at least one of `groupby`, `metrics`, or `percent_metrics` must have a value.
- **Row Limits**: The `row_limit` controls how many rows are retrieved from the database. For `show_totals`, the row limit does not apply to the total calculation.
- **Percentage Metrics**: Percentage metrics are calculated only from data within the row limit, not from the entire dataset.
