# Bullet Chart (`bullet`)

## Description
A Bullet Chart is a variation of a bar chart designed to showcase the progress of a single metric against a given target. The chart features a horizontal bar representing the actual metric value, with background shading for contextual ranges and markers (triangles or lines) to indicate targets or reference points. The higher the fill of the bar, the closer the metric is to achieving its target.

## When to Use
Use a Bullet Chart when you need to display performance metrics against goals or benchmarks in a compact, easy-to-read format. This chart type is ideal for KPI dashboards where space efficiency is important and you want to show not just current performance, but also contextual ranges (like "poor", "satisfactory", "good") and specific target values.

## Example Use Cases
- Tracking sales revenue against quarterly targets with performance ranges
- Monitoring server response times against SLA thresholds
- Displaying customer satisfaction scores with industry benchmark markers
- Showing project completion percentage against planned milestones
- Comparing actual expenses against budget allocations with warning zones

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `bullet` |
| datasource_id | integer | Yes | ID of the datasource |
| datasource_type | string | Yes | Type of datasource (e.g., 'table', 'query') |
| params | string | Yes | JSON string containing chart-specific parameters |
| description | string | No | Chart description |
| owners | array | No | List of owner user IDs |
| cache_timeout | integer | No | Cache timeout in seconds |
| dashboards | array | No | List of dashboard IDs to add chart to |
| certified_by | string | No | Name of person or group that certified this chart |
| certification_details | string | No | Details about the certification |

### params Object
The `params` field must be a JSON string containing an object with the following properties:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| metric | object/string | Yes | - | Metric to display. Can be an adhoc metric object with aggregation function on a column, or a saved metric identifier. This represents the main value shown as the bar in the chart. |
| adhoc_filters | array | No | [] | Array of adhoc filter objects to filter the data. Each filter can be a simple column filter or custom SQL filter. |
| ranges | string | No | "" | Comma-separated list of numeric values representing background ranges to highlight with shading (e.g., "50,75,100"). These ranges provide context for the metric value. |
| range_labels | string | No | "" | Comma-separated list of labels corresponding to the ranges (e.g., "Poor,Fair,Good"). Must match the number of ranges if provided. |
| markers | string | No | "" | Comma-separated list of numeric values to mark with triangle indicators on the chart (e.g., "60,90"). Useful for showing targets or benchmarks. |
| marker_labels | string | No | "" | Comma-separated list of labels for the marker triangles. Must match the number of markers if provided. |
| marker_lines | string | No | "" | Comma-separated list of numeric values to mark with vertical lines on the chart (e.g., "80"). Provides additional reference points. |
| marker_line_labels | string | No | "" | Comma-separated list of labels for the marker lines. Must match the number of marker_lines if provided. |

#### Metric Object Structure
When using an adhoc metric, the metric field should be an object with:
- `label`: Display name for the metric
- `expressionType`: Either "SIMPLE" (for column with aggregation) or "SQL" (for custom SQL)
- `column`: Column object (for SIMPLE type) with `column_name` and `type`
- `aggregate`: Aggregation function (for SIMPLE type) like "SUM", "AVG", "COUNT", etc.
- `sqlExpression`: Custom SQL expression (for SQL type)

#### Adhoc Filter Object Structure
Each filter in the `adhoc_filters` array should have:
- `clause`: Either "WHERE" or "HAVING"
- `expressionType`: Either "SIMPLE" or "SQL"
- `subject`: Column name (for SIMPLE type)
- `operator`: Filter operator like "==", "!=", ">", "<", "IN", "NOT IN", etc. (for SIMPLE type)
- `comparator`: Value to compare against (for SIMPLE type)
- `sqlExpression`: Custom SQL WHERE clause (for SQL type)

### Example Request
```json
{
  "slice_name": "Q4 Sales Performance",
  "viz_type": "bullet",
  "datasource_id": 123,
  "datasource_type": "table",
  "description": "Sales performance tracking against Q4 targets",
  "owners": [1, 5],
  "dashboards": [10],
  "params": "{\"metric\":{\"label\":\"Total Sales\",\"expressionType\":\"SIMPLE\",\"column\":{\"column_name\":\"sales_amount\",\"type\":\"DOUBLE\"},\"aggregate\":\"SUM\"},\"adhoc_filters\":[{\"clause\":\"WHERE\",\"expressionType\":\"SIMPLE\",\"subject\":\"quarter\",\"operator\":\"==\",\"comparator\":\"Q4\"}],\"ranges\":\"50000,75000,100000\",\"range_labels\":\"Below Target,On Track,Exceeds Target\",\"markers\":\"80000\",\"marker_labels\":\"Q4 Goal\",\"marker_lines\":\"90000\",\"marker_line_labels\":\"Stretch Goal\"}"
}
```

#### Expanded params Object (for clarity):
```json
{
  "metric": {
    "label": "Total Sales",
    "expressionType": "SIMPLE",
    "column": {
      "column_name": "sales_amount",
      "type": "DOUBLE"
    },
    "aggregate": "SUM"
  },
  "adhoc_filters": [
    {
      "clause": "WHERE",
      "expressionType": "SIMPLE",
      "subject": "quarter",
      "operator": "==",
      "comparator": "Q4"
    }
  ],
  "ranges": "50000,75000,100000",
  "range_labels": "Below Target,On Track,Exceeds Target",
  "markers": "80000",
  "marker_labels": "Q4 Goal",
  "marker_lines": "90000",
  "marker_line_labels": "Stretch Goal"
}
```

## Notes
- The Bullet Chart is part of the legacy NVD3 chart library and uses the legacy API (`useLegacyApi: true`)
- All numeric values in ranges, markers, and marker_lines should be provided as comma-separated strings
- Labels for ranges, markers, and marker_lines are optional but recommended for clarity
- The number of labels should match the number of corresponding values
- This chart type is categorized as a "KPI" visualization and is commonly used in business reporting contexts
