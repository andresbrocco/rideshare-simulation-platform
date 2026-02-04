# Funnel Chart (`funnel`)

## Description
The Funnel Chart visualizes how a metric changes as it progresses through sequential stages, displayed as progressively narrowing horizontal or vertical segments. This chart is powered by Apache ECharts and is useful for tracking conversion rates and identifying drop-off points in multi-stage processes, with each stage's width proportional to its value relative to other stages.

## When to Use
Use a Funnel Chart when you need to visualize sequential stages where values decrease progressively, such as conversion funnels, sales pipelines, or multi-step workflows. This chart type is particularly effective for identifying bottlenecks and drop-off rates between consecutive stages in a process.

## Example Use Cases
- Sales pipeline tracking from leads to closed deals
- E-commerce conversion funnel from product views to purchases
- User onboarding flow completion rates across registration steps
- Marketing campaign performance from impressions to conversions
- Application form completion tracking through multiple steps

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `funnel` |
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

The `params` field must be a JSON-encoded string containing the following parameters:

#### Query Parameters
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| groupby | array | Yes | `[]` | Array of column names to group by (categories for funnel stages) |
| metric | string or object | Yes | - | Metric to display (aggregation function or custom SQL) |
| adhoc_filters | array | No | `[]` | Array of ad-hoc filter objects for filtering data |
| row_limit | integer | No | `10` | Maximum number of rows to display in the funnel |
| sort_by_metric | boolean | No | `true` | Whether to sort results by the metric in descending order |
| percent_calculation_type | string | No | `'first_step'` | How to calculate percentages. Options: `'first_step'` (from first stage), `'prev_step'` (from previous stage), `'total'` (percent of total) |

#### Chart Options
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| color_scheme | string | No | Default theme | Color scheme for rendering the chart |
| show_legend | boolean | No | `true` | Whether to display the legend |
| legendType | string | No | `'scroll'` | Legend type. Options: `'scroll'`, `'plain'` |
| legendOrientation | string | No | `'top'` | Legend position. Options: `'top'`, `'bottom'`, `'left'`, `'right'` |
| legendMargin | integer | No | - | Additional padding for legend in pixels |
| legendSort | string | No | `null` | Sort order for legend items. Options: `'asc'`, `'desc'`, `null` (sort by data) |

#### Label Options
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| label_type | string | No | `'key'` | Content to show in labels. Options: `'key'` (category name), `'value'`, `'percent'`, `'key_value'`, `'key_percent'`, `'key_value_percent'`, `'value_percent'` |
| tooltip_label_type | string | No | `'key_value_percent'` | Content to show in tooltips. Options: same as label_type (except `'value_percent'` not available) |
| number_format | string | No | `'SMART_NUMBER'` | D3 number format string for displaying values (e.g., `'.2f'`, `',.0f'`, `'.2%'`) |
| currency_format | object | No | - | Currency formatting configuration with symbol and position |
| show_labels | boolean | No | `true` | Whether to display labels on funnel segments |
| show_tooltip_labels | boolean | No | `true` | Whether to display labels in tooltips |

### Example Request

```json
{
  "slice_name": "Sales Conversion Funnel",
  "description": "Tracks customer journey from leads to closed deals",
  "viz_type": "funnel",
  "datasource_id": 123,
  "datasource_type": "table",
  "params": "{\"groupby\":[\"stage_name\"],\"metric\":{\"expressionType\":\"SIMPLE\",\"column\":{\"column_name\":\"count\",\"type\":\"BIGINT\"},\"aggregate\":\"SUM\",\"label\":\"Total Count\"},\"adhoc_filters\":[{\"expressionType\":\"SIMPLE\",\"subject\":\"created_date\",\"operator\":\"TEMPORAL_RANGE\",\"comparator\":\"Last month\",\"clause\":\"WHERE\"}],\"row_limit\":10,\"sort_by_metric\":true,\"percent_calculation_type\":\"first_step\",\"color_scheme\":\"supersetColors\",\"show_legend\":true,\"legendType\":\"scroll\",\"legendOrientation\":\"top\",\"label_type\":\"key_value_percent\",\"tooltip_label_type\":\"key_value_percent\",\"number_format\":\",.0f\",\"show_labels\":true,\"show_tooltip_labels\":true}",
  "cache_timeout": 3600,
  "owners": [1],
  "dashboards": [5]
}
```

### Example params Object (before JSON encoding)

```json
{
  "groupby": ["stage_name"],
  "metric": {
    "expressionType": "SIMPLE",
    "column": {
      "column_name": "count",
      "type": "BIGINT"
    },
    "aggregate": "SUM",
    "label": "Total Count"
  },
  "adhoc_filters": [
    {
      "expressionType": "SIMPLE",
      "subject": "created_date",
      "operator": "TEMPORAL_RANGE",
      "comparator": "Last month",
      "clause": "WHERE"
    }
  ],
  "row_limit": 10,
  "sort_by_metric": true,
  "percent_calculation_type": "first_step",
  "color_scheme": "supersetColors",
  "show_legend": true,
  "legendType": "scroll",
  "legendOrientation": "top",
  "legendMargin": 50,
  "legendSort": null,
  "label_type": "key_value_percent",
  "tooltip_label_type": "key_value_percent",
  "number_format": ",.0f",
  "show_labels": true,
  "show_tooltip_labels": true
}
```

## Response Format

A successful chart creation returns a JSON object with the chart details:

```json
{
  "id": 456,
  "slice_name": "Sales Conversion Funnel",
  "description": "Tracks customer journey from leads to closed deals",
  "viz_type": "funnel",
  "datasource_id": 123,
  "datasource_type": "table",
  "cache_timeout": 3600,
  "owners": [
    {
      "id": 1,
      "username": "admin"
    }
  ],
  "params": "{...}",
  "created_on_delta_humanized": "a few seconds ago",
  "changed_on_delta_humanized": "a few seconds ago"
}
```

## Notes

### Label Type Options Explained
- **key**: Shows only the category name (e.g., "Lead")
- **value**: Shows only the numeric value (e.g., "1,500")
- **percent**: Shows only the percentage (e.g., "100%")
- **key_value**: Shows category and value (e.g., "Lead: 1,500")
- **key_percent**: Shows category and percentage (e.g., "Lead: 100%")
- **key_value_percent**: Shows all three (e.g., "Lead: 1,500 (100%)")
- **value_percent**: Shows value and percentage (e.g., "1,500 (100%)" - only for labels, not tooltips)

### Percentage Calculation Types
- **first_step**: Calculates each stage's percentage relative to the first stage (shows cumulative conversion)
- **prev_step**: Calculates each stage's percentage relative to the previous stage (shows stage-to-stage drop-off)
- **total**: Calculates each stage's percentage as a portion of the sum of all stages

### Number Format
The `number_format` field accepts D3 format strings. Common examples:
- `SMART_NUMBER`: Automatically formats numbers with appropriate suffixes (K, M, B)
- `,.0f`: Comma-separated integer (e.g., 1,234)
- `.2f`: Decimal with 2 places (e.g., 1234.56)
- `.2%`: Percentage with 2 decimal places (e.g., 12.34%)
- `$,.2f`: Currency format (e.g., $1,234.56)

For more format options, see [D3 format documentation](https://github.com/d3/d3-format).

### Interactive Features
The Funnel Chart supports these interactive behaviors:
- **Drill to Detail**: Click on funnel segments to explore underlying data
- **Drill By**: Analyze data by additional dimensions
- **Interactive Chart**: Hover over segments for detailed tooltips

## API Endpoints

- **Create Chart**: `POST /api/v1/chart/`
- **Update Chart**: `PUT /api/v1/chart/{id}`
- **Get Chart**: `GET /api/v1/chart/{id}`
- **Delete Chart**: `DELETE /api/v1/chart/{id}`
- **Get Chart Data**: `POST /api/v1/chart/data`

For complete API documentation, visit the Swagger UI at `/swagger/v1` on your Superset instance.
