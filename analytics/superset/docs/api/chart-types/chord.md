# Chord Diagram (`chord`)

## Description
A Chord Diagram is a circular visualization that shows the flow or relationships between categories using arcs (chords) that connect different segments around a circle. The thickness of each chord represents the magnitude of the relationship, and importantly, the value and corresponding thickness can be different for each direction of the relationship, making it ideal for displaying asymmetric flows.

## When to Use
Use a Chord Diagram when you need to visualize relationships, flows, or connections between different categories where the direction and magnitude matter. This chart is particularly effective when you want to show reciprocal relationships or when the flow from A to B differs from the flow from B to A.

## Example Use Cases
- Visualizing migration patterns between countries or regions (showing both immigration and emigration flows)
- Analyzing trade relationships between different business units or partners
- Displaying communication patterns between teams or departments
- Showing financial flows between different accounts or entities
- Mapping relationships between community channels or social network connections

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `chord` |
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
The `params` field must be a JSON string containing an object with the following properties:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| groupby | array | Yes | - | Single column defining the source of the relationship. Must contain exactly one column. |
| columns | array | Yes | - | Single column defining the target of the relationship. Must contain exactly one column. |
| metric | object/string | Yes | - | Metric to aggregate for determining the thickness of the chords. Can be an adhoc metric object or a saved metric name. |
| adhoc_filters | array | No | [] | List of adhoc filter objects for filtering the data |
| row_limit | integer | No | 10000 | Maximum number of rows to compute in the query (can be up to SQL_MAX_ROW configuration) |
| sort_by_metric | boolean | No | false | Whether to sort results by the selected metric in descending order |
| y_axis_format | string | No | SMART_NUMBER | Number format for displaying values (D3 format string) |
| color_scheme | string | No | (default scheme) | Color scheme for rendering the chart segments |

#### Field Details

**groupby**
- Must be an array with exactly one column
- Represents the source node in the chord diagram
- Example: `["country_from"]`

**columns**
- Must be an array with exactly one column
- Represents the target node in the chord diagram
- Cannot be the same column as groupby
- Example: `["country_to"]`

**metric**
- Defines the value that determines chord thickness
- Can be an adhoc metric object with aggregation function:
  ```json
  {
    "expressionType": "SIMPLE",
    "column": {
      "column_name": "amount",
      "type": "DOUBLE"
    },
    "aggregate": "SUM",
    "label": "Sum of Amount"
  }
  ```
- Or a string referencing a saved metric: `"count"`

**adhoc_filters**
- Array of filter objects to apply to the data
- Each filter can be simple or SQL-based
- Example simple filter:
  ```json
  {
    "expressionType": "SIMPLE",
    "clause": "WHERE",
    "subject": "year",
    "operator": "==",
    "comparator": "2023"
  }
  ```

**y_axis_format**
- Accepts D3 format strings
- Common formats: `SMART_NUMBER`, `.2f`, `.3s`, `,.0f`, `.1%`
- Controls how numeric values are displayed in tooltips and labels

**color_scheme**
- Name of a registered color scheme
- Common schemes: `supersetColors`, `d3Category10`, `googleCategory10c`, `tableau10`

### Example Request

```json
{
  "slice_name": "International Migration Flows 2023",
  "viz_type": "chord",
  "datasource_id": 42,
  "datasource_type": "table",
  "description": "Chord diagram showing migration patterns between countries",
  "params": "{\"groupby\": [\"origin_country\"], \"columns\": [\"destination_country\"], \"metric\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"migration_count\", \"type\": \"BIGINT\"}, \"aggregate\": \"SUM\", \"label\": \"Total Migrants\"}, \"adhoc_filters\": [{\"expressionType\": \"SIMPLE\", \"clause\": \"WHERE\", \"subject\": \"year\", \"operator\": \"==\", \"comparator\": \"2023\"}], \"row_limit\": 10000, \"sort_by_metric\": true, \"y_axis_format\": \",.0f\", \"color_scheme\": \"supersetColors\"}",
  "cache_timeout": 3600,
  "owners": [1],
  "dashboards": [5]
}
```

### Minimal Example Request

```json
{
  "slice_name": "Basic Chord Diagram",
  "viz_type": "chord",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"groupby\": [\"source\"], \"columns\": [\"target\"], \"metric\": \"count\"}"
}
```

## Response Format

### Success Response (201 Created)

```json
{
  "id": 123,
  "result": {
    "slice_name": "International Migration Flows 2023",
    "viz_type": "chord",
    "datasource_id": 42,
    "datasource_type": "table",
    "description": "Chord diagram showing migration patterns between countries",
    "params": "{\"groupby\": [\"origin_country\"], \"columns\": [\"destination_country\"], \"metric\": {...}, ...}",
    "cache_timeout": 3600,
    "owners": [1],
    "dashboards": [5],
    "changed_on": "2023-10-15T14:30:00",
    "uuid": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"
  }
}
```

## Notes

- This is a **legacy chart type** (`useLegacyApi: true`), which means it uses the older API format
- The chord diagram is part of the "Flow" category of visualizations
- Based on [D3 Chord Layout](https://github.com/d3/d3-chord)
- The visualization is circular with proportional relationships
- Both the source (groupby) and target (columns) must be single columns - multi-column selections are not supported
- The metric determines the thickness of the chords connecting the segments
- Directional flows are supported - the chord from A to B can have a different thickness than the chord from B to A based on the aggregated metric values
