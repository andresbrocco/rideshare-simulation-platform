# Sankey Diagram (`sankey_v2`)

## Description
The Sankey Chart visually tracks the movement and transformation of values across system stages. Nodes represent stages, connected by links depicting value flow. Node height corresponds to the visualized metric, providing a clear representation of value distribution and transformation. This chart is powered by Apache ECharts.

## When to Use
Use a Sankey Chart when you need to visualize flows and transformations between different stages or categories in a system. This chart type is particularly effective for showing how quantities are distributed, merged, or split across multiple pathways, making it ideal for understanding value transfers and identifying major flow patterns.

## Example Use Cases
- Visualizing energy or material flows in manufacturing processes
- Tracking budget allocation across departments and projects
- Analyzing website traffic flow between different pages or sections
- Displaying customer journey paths through different touchpoints
- Showing data transfer or network traffic between systems
- Mapping supply chain flows from suppliers to customers
- Analyzing resource consumption and distribution in utilities

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `sankey_v2` |
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
| source | string | Yes | - | The column to be used as the source of the edge. Must be a single column name. |
| target | string | Yes | - | The column to be used as the target of the edge. Must be a single column name. |
| metric | string or object | Yes | - | Metric to display (aggregation function or custom SQL). Determines the width of the flow. |
| adhoc_filters | array | No | `[]` | Array of ad-hoc filter objects for filtering data |
| row_limit | integer | No | `10000` | Maximum number of rows to compute in the query (can be up to SQL_MAX_ROW configuration) |
| sort_by_metric | boolean | No | `false` | Whether to sort results by the selected metric in descending order |

#### Chart Options
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| color_scheme | string | No | Default theme | Color scheme for rendering the chart nodes and links |

#### Field Details

**source**
- Must be a single column name (not an array)
- Represents the starting point of the flow
- Each unique value in this column becomes a source node
- Example: `"department_from"`

**target**
- Must be a single column name (not an array)
- Represents the destination of the flow
- Each unique value in this column becomes a target node
- Can contain values that also appear in the source column (creating multi-level flows)
- Example: `"department_to"`

**metric**
- Defines the value that determines the width/height of the flow links and nodes
- Can be an adhoc metric object with aggregation function:
  ```json
  {
    "expressionType": "SIMPLE",
    "column": {
      "column_name": "amount",
      "type": "DOUBLE"
    },
    "aggregate": "SUM",
    "label": "Total Amount"
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
    "comparator": "2024"
  }
  ```
- Example temporal filter:
  ```json
  {
    "expressionType": "SIMPLE",
    "subject": "created_date",
    "operator": "TEMPORAL_RANGE",
    "comparator": "Last quarter",
    "clause": "WHERE"
  }
  ```

**color_scheme**
- Name of a registered color scheme
- Common schemes: `supersetColors`, `d3Category10`, `googleCategory10c`, `tableau10`
- Colors are assigned to nodes and their corresponding flows

### Example Request

```json
{
  "slice_name": "Budget Flow by Department",
  "description": "Visualizes budget allocation flow from departments to projects",
  "viz_type": "sankey_v2",
  "datasource_id": 123,
  "datasource_type": "table",
  "params": "{\"source\":\"department\",\"target\":\"project\",\"metric\":{\"expressionType\":\"SIMPLE\",\"column\":{\"column_name\":\"budget_amount\",\"type\":\"DOUBLE\"},\"aggregate\":\"SUM\",\"label\":\"Total Budget\"},\"adhoc_filters\":[{\"expressionType\":\"SIMPLE\",\"subject\":\"fiscal_year\",\"operator\":\"==\",\"comparator\":\"2024\",\"clause\":\"WHERE\"}],\"row_limit\":10000,\"sort_by_metric\":true,\"color_scheme\":\"supersetColors\"}",
  "cache_timeout": 3600,
  "owners": [1],
  "dashboards": [5]
}
```

### Example params Object (before JSON encoding)

```json
{
  "source": "department",
  "target": "project",
  "metric": {
    "expressionType": "SIMPLE",
    "column": {
      "column_name": "budget_amount",
      "type": "DOUBLE"
    },
    "aggregate": "SUM",
    "label": "Total Budget"
  },
  "adhoc_filters": [
    {
      "expressionType": "SIMPLE",
      "subject": "fiscal_year",
      "operator": "==",
      "comparator": "2024",
      "clause": "WHERE"
    }
  ],
  "row_limit": 10000,
  "sort_by_metric": true,
  "color_scheme": "supersetColors"
}
```

### Minimal Example Request

```json
{
  "slice_name": "Basic Sankey Flow",
  "viz_type": "sankey_v2",
  "datasource_id": 123,
  "datasource_type": "table",
  "params": "{\"source\":\"from_node\",\"target\":\"to_node\",\"metric\":\"count\"}"
}
```

## Response Format

A successful chart creation returns a JSON object with the chart details:

```json
{
  "id": 456,
  "slice_name": "Budget Flow by Department",
  "description": "Visualizes budget allocation flow from departments to projects",
  "viz_type": "sankey_v2",
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
  "changed_on_delta_humanized": "a few seconds ago",
  "uuid": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"
}
```

## Notes

### Data Structure Requirements
- Your data should have at least three columns: source, target, and a value column
- Each row represents a single flow/connection between a source and target
- The metric aggregation determines the magnitude of each flow
- Multiple rows with the same source-target pair will be aggregated based on the selected metric

### Multi-Level Flows
The Sankey chart supports multi-level flows where:
- A node can be both a source and a target
- Values flow from left to right through intermediate stages
- Example: `Department A → Project X → Task 1` can be created with two rows:
  - Row 1: `department='Dept A', project='Project X', amount=1000`
  - Row 2: `project='Project X', task='Task 1', amount=1000`

### Node Height Calculation
- Node height is proportional to the sum of all flows entering or leaving that node
- The height represents the total magnitude passing through that stage
- Larger values result in taller nodes, making it easy to identify major flow contributors

### Interactive Features
The Sankey Chart supports these interactive behaviors:
- **Hover**: Display detailed information about flows and nodes in tooltips
- **Interactive Chart**: Dynamic highlighting of connected flows when hovering over nodes
- **Drill to Detail**: Click on flows or nodes to explore underlying data (when configured)

### Common Use Patterns

**Simple Two-Stage Flow**
```json
{
  "source": "category_a",
  "target": "category_b",
  "metric": "sum__value"
}
```

**Multi-Stage Flow**
Use a UNION query or create separate source-target pairs in your data:
- Stage 1 to Stage 2: source = stage1_col, target = stage2_col
- Stage 2 to Stage 3: source = stage2_col, target = stage3_col

### Comparison with Chord Diagram
While both visualize flows between categories:
- **Sankey**: Shows directional flows from left to right, emphasizing progression through stages
- **Chord**: Shows bidirectional relationships in a circular layout, emphasizing reciprocal connections

Choose Sankey when you want to emphasize progression and transformation; choose Chord when relationships are reciprocal and circular representation is more appropriate.

## API Endpoints

- **Create Chart**: `POST /api/v1/chart/`
- **Update Chart**: `PUT /api/v1/chart/{id}`
- **Get Chart**: `GET /api/v1/chart/{id}`
- **Delete Chart**: `DELETE /api/v1/chart/{id}`
- **Get Chart Data**: `POST /api/v1/chart/data`

For complete API documentation, visit the Swagger UI at `/swagger/v1` on your Superset instance.
