# Parallel Coordinates (`para`)

## Description
The Parallel Coordinates chart visualizes multivariate data by plotting individual metrics for each row as vertical axes that are linked together as lines. Each row in the dataset becomes a polyline that traverses across the vertical axes, with the position on each axis representing the value of that metric. This chart is particularly useful for identifying patterns, correlations, and clusters across multiple dimensions simultaneously.

## When to Use
Use this chart type when you need to compare multiple metrics across all samples or rows in your dataset. It excels at revealing relationships between variables and identifying outliers or clusters in multivariate data. The chart is most effective when you have 3-10 metrics to compare, as too many axes can become difficult to interpret.

## Example Use Cases
- Comparing multiple performance indicators (KPIs) across different business units or time periods
- Analyzing product characteristics (price, quality, durability, customer satisfaction) across multiple products
- Evaluating employee metrics (experience, productivity, attendance, satisfaction) across departments
- Studying environmental measurements (temperature, humidity, pressure, pollution levels) across monitoring stations
- Investigating financial ratios (liquidity, profitability, efficiency, leverage) across companies or time periods

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `para` |
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
The `params` field must be a JSON-encoded string containing the following chart-specific parameters:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| metrics | array | Yes | [] | List of metrics to display as parallel axes. Each metric appears as a vertical axis in the chart. Can be specified as strings (for saved metrics) or adhoc metric objects. |
| series | string | No | null | Dimension column that defines grouping of entities. Each series is represented by a specific color in the chart. When specified, lines are colored by this dimension. |
| secondary_metric | object/string | No | null | Metric used to determine the color intensity of each line when a color scheme is applied. Also known as the "Color Metric". |
| adhoc_filters | array | No | [] | List of adhoc filters to apply to the data. Each filter is an object with properties like clause, subject, operator, comparator, and expressionType. |
| row_limit | integer | No | 10000 | Maximum number of rows to compute in the query that is the source of the data. Limits the number of lines displayed in the chart. |
| limit | integer | No | null | Series limit. When specified with timeseries_limit_metric, limits the number of series displayed using a subquery. Useful when grouping by high cardinality columns. |
| timeseries_limit_metric | object/string | No | null | Metric used to limit and order series when `limit` is specified. Determines which series to include when the limit is reached. |
| order_desc | boolean | No | true | When true, sorts results by the timeseries_limit_metric in descending order. When false, sorts in ascending order. Only applies when timeseries_limit_metric is set. |
| show_datatable | boolean | No | false | Whether to display an interactive data table below the chart showing the raw data values. |
| include_series | boolean | No | false | Whether to include the series name as an additional axis in the parallel coordinates visualization. |
| linear_color_scheme | string | No | (default sequential scheme) | Sequential color scheme for rendering the chart. Used to color lines based on the secondary_metric value. Must be a valid sequential color scheme name. |

### Metric Object Format
Metrics can be specified as either:

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
  "slice_name": "Business Unit Performance Metrics",
  "viz_type": "para",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"metrics\": [{\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"revenue\", \"type\": \"DOUBLE\"}, \"aggregate\": \"SUM\", \"label\": \"Total Revenue\"}, {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"expenses\", \"type\": \"DOUBLE\"}, \"aggregate\": \"SUM\", \"label\": \"Total Expenses\"}, {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"customer_satisfaction\", \"type\": \"DOUBLE\"}, \"aggregate\": \"AVG\", \"label\": \"Avg Customer Satisfaction\"}, {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"employee_count\", \"type\": \"INTEGER\"}, \"aggregate\": \"SUM\", \"label\": \"Total Employees\"}], \"series\": \"business_unit\", \"secondary_metric\": {\"expressionType\": \"SQL\", \"sqlExpression\": \"SUM(revenue) - SUM(expenses)\", \"label\": \"Net Profit\"}, \"adhoc_filters\": [{\"clause\": \"WHERE\", \"subject\": \"fiscal_year\", \"operator\": \"==\", \"comparator\": \"2024\", \"expressionType\": \"SIMPLE\"}], \"row_limit\": 1000, \"limit\": 20, \"timeseries_limit_metric\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"revenue\", \"type\": \"DOUBLE\"}, \"aggregate\": \"SUM\", \"label\": \"Total Revenue\"}, \"order_desc\": true, \"show_datatable\": true, \"include_series\": false, \"linear_color_scheme\": \"blue_white_yellow\"}",
  "description": "Parallel coordinates visualization comparing key performance metrics across business units",
  "owners": [1]
}
```

## Notes
- This chart type is marked as **Legacy** and uses an external library from [syntagmatic/parallel-coordinates](https://syntagmatic.github.io/parallel-coordinates)
- Each metric specified in the `metrics` array becomes a vertical axis in the chart
- Each row in the data becomes a line (polyline) traversing across all the axes
- The `series` field allows grouping and coloring lines by category
- The `secondary_metric` (Color Metric) determines the color intensity of each line based on its value, using the specified linear color scheme
- When `include_series` is true, the series dimension is added as an additional axis in the visualization
- The chart is interactive, allowing users to brush (select ranges) on axes to filter and highlight specific data subsets
- The `show_datatable` option provides a tabular view of the data below the chart for detailed inspection
- This visualization works best with normalized or standardized data, as axes with different scales can make comparison difficult
- Too many metrics (>10) or too many rows (>1000) can make the visualization cluttered and hard to interpret
- The chart supports brushing interactions where you can drag on an axis to filter the visible lines
