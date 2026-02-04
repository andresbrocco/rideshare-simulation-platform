# Graph Chart (`graph_chart`)

## Description
A Graph Chart displays connections between entities in a network structure, visualizing nodes and the relationships (edges) between them. The chart can be configured with either a force-directed layout (where nodes push away from each other) or a circular layout. Nodes can be sized and colored based on their properties, and edges can show directionality with arrows. This chart is ideal for mapping complex relationships and identifying key nodes in a network.

## When to Use
Use a Graph Chart when you need to visualize network relationships, connections, or dependencies between entities. This chart is particularly effective for understanding network topology, identifying central or important nodes, and analyzing the flow or relationships in connected systems.

## Example Use Cases
- Visualizing social network connections and influence patterns
- Mapping organizational hierarchies and reporting relationships
- Analyzing service dependencies in microservices architectures
- Displaying knowledge graphs and concept relationships
- Showing supply chain networks and logistics flows
- Mapping communication patterns between systems or teams

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `graph_chart` |
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
| source | string | Yes | - | Column containing the source node names |
| target | string | Yes | - | Column containing the target node names |
| metric | object/string | No | - | Metric to aggregate for determining edge thickness and node size. Can be an adhoc metric object or a saved metric name. |
| source_category | string | No | - | Column for categorizing source nodes (affects coloring). If a node has multiple categories, only the first is used. |
| target_category | string | No | - | Column for categorizing target nodes (affects coloring) |
| adhoc_filters | array | No | [] | List of adhoc filter objects for filtering the data |
| row_limit | integer | No | 10000 | Maximum number of rows to compute in the query (can be up to SQL_MAX_ROW configuration) |
| color_scheme | string | No | (default scheme) | Color scheme for rendering chart nodes |
| layout | string | No | "force" | Graph layout algorithm. Options: "force" (force-directed), "circular" |
| roam | boolean/string | No | true | Enable panning and zooming. Options: false, "scale" (zoom only), "move" (pan only), true (both) |
| draggable | boolean | No | false | Enable node dragging in force layout mode (only applicable when layout is "force") |
| selectedMode | boolean/string | No | "single" | Node selection mode. Options: false (disabled), "single", "multiple" |
| showSymbolThreshold | integer | No | 0 | Minimum value for label to be displayed on graph |
| baseNodeSize | number | No | 20 | Median node size. The largest node will be 4 times larger than the smallest |
| baseEdgeWidth | number | No | 3 | Median edge width. The thickest edge will be 4 times thicker than the thinnest |
| edgeSymbol | string | No | "none,arrow" | Symbol of two ends of edge line. Options: "none,none", "none,arrow", "circle,arrow", "circle,circle" |
| edgeLength | integer | No | 400 | Edge length between nodes in force layout (range: 100-1000, only applicable when layout is "force") |
| gravity | number | No | 0.3 | Strength to pull the graph toward center in force layout (range: 0.1-1, only applicable when layout is "force") |
| repulsion | integer | No | 1000 | Repulsion strength between nodes in force layout (range: 100-3000, only applicable when layout is "force") |
| friction | number | No | 0.2 | Friction between nodes in force layout (range: 0.1-1, only applicable when layout is "force") |
| show_legend | boolean | No | true | Whether to display a legend for the chart |
| legendType | string | No | "scroll" | Legend type. Options: "scroll", "plain" |
| legendOrientation | string | No | "top" | Legend orientation. Options: "top", "bottom", "left", "right" |
| legendMargin | integer | No | - | Additional padding for legend |
| legendSort | string | No | null | Sort legend. Options: "asc" (label ascending), "desc" (label descending), null (sort by data) |

#### Field Details

**source**
- Required field specifying the column containing source node names
- Each unique value becomes a node in the graph
- Example: `"user_id"` or `"service_name"`

**target**
- Required field specifying the column containing target node names
- Each unique value becomes a node in the graph
- Connects to source nodes to form edges
- Example: `"friend_id"` or `"dependent_service"`

**metric**
- Defines the value that determines edge thickness and node size
- Can be an adhoc metric object with aggregation function:
  ```json
  {
    "expressionType": "SIMPLE",
    "column": {
      "column_name": "connection_strength",
      "type": "DOUBLE"
    },
    "aggregate": "SUM",
    "label": "Total Connections"
  }
  ```
- Or a string referencing a saved metric: `"count"`

**source_category / target_category**
- Optional columns for grouping and coloring nodes by category
- If a node appears with multiple categories, only the first category encountered is used
- Categories are assigned colors based on the selected color scheme
- Example: `"department"` or `"node_type"`

**layout**
- `"force"`: Uses a force-directed algorithm where nodes repel each other and edges act like springs. Best for organic, natural-looking networks.
- `"circular"`: Arranges nodes in a circle. Best for cleaner, more organized visualizations.

**roam**
- Controls user interaction with the graph viewport
- `false`: No zooming or panning allowed
- `"scale"`: Only zooming allowed
- `"move"`: Only panning allowed
- `true`: Both zooming and panning allowed

**draggable**
- Only applicable when `layout` is `"force"`
- Allows users to click and drag nodes to reposition them
- Helps explore the network by manually adjusting node positions

**selectedMode**
- Controls how users can select nodes
- `false`: Node selection disabled
- `"single"`: Only one node can be selected at a time
- `"multiple"`: Multiple nodes can be selected simultaneously

**showSymbolThreshold**
- Controls label visibility based on node/edge values
- Nodes or edges with values below this threshold will not show labels
- Useful for decluttering dense graphs

**baseNodeSize / baseEdgeWidth**
- Control the median size for nodes and edge thickness
- The actual sizes are scaled based on metric values
- Size ratio between largest and smallest is 4:1

**edgeSymbol**
- Controls the visual style of edge endpoints
- Format is "start,end" where each can be "none", "circle", or "arrow"
- Examples:
  - `"none,arrow"`: Directed edges with arrows pointing to target
  - `"circle,circle"`: Undirected edges with circles at both ends
  - `"none,none"`: Simple lines with no decorations

**Force Layout Parameters (edgeLength, gravity, repulsion, friction)**
- These parameters only apply when `layout` is `"force"`
- `edgeLength`: Ideal distance between connected nodes (100-1000)
- `gravity`: How strongly nodes are pulled toward the center (0.1-1)
- `repulsion`: How strongly nodes push away from each other (100-3000)
- `friction`: Dampening force that slows down node movement (0.1-1)
- Adjust these to control the spread and stability of the force-directed layout

**adhoc_filters**
- Array of filter objects to apply to the data
- Each filter can be simple or SQL-based
- Example simple filter:
  ```json
  {
    "expressionType": "SIMPLE",
    "clause": "WHERE",
    "subject": "status",
    "operator": "==",
    "comparator": "active"
  }
  ```

**color_scheme**
- Name of a registered color scheme
- Common schemes: `supersetColors`, `d3Category10`, `googleCategory10c`, `tableau10`

### Example Request

```json
{
  "slice_name": "Microservices Dependency Graph",
  "viz_type": "graph_chart",
  "datasource_id": 42,
  "datasource_type": "table",
  "description": "Force-directed graph showing service dependencies and call volumes",
  "params": "{\"source\": \"calling_service\", \"target\": \"called_service\", \"metric\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"call_count\", \"type\": \"BIGINT\"}, \"aggregate\": \"SUM\", \"label\": \"Total Calls\"}, \"source_category\": \"service_tier\", \"target_category\": \"service_tier\", \"adhoc_filters\": [{\"expressionType\": \"SIMPLE\", \"clause\": \"WHERE\", \"subject\": \"environment\", \"operator\": \"==\", \"comparator\": \"production\"}], \"row_limit\": 10000, \"color_scheme\": \"supersetColors\", \"layout\": \"force\", \"roam\": true, \"draggable\": false, \"selectedMode\": \"single\", \"showSymbolThreshold\": 0, \"baseNodeSize\": 20, \"baseEdgeWidth\": 3, \"edgeSymbol\": \"none,arrow\", \"edgeLength\": 400, \"gravity\": 0.3, \"repulsion\": 1000, \"friction\": 0.2, \"show_legend\": true, \"legendType\": \"scroll\", \"legendOrientation\": \"top\"}",
  "cache_timeout": 3600,
  "owners": [1],
  "dashboards": [5]
}
```

### Minimal Example Request

```json
{
  "slice_name": "Basic Network Graph",
  "viz_type": "graph_chart",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"source\": \"node_from\", \"target\": \"node_to\"}"
}
```

### Circular Layout Example Request

```json
{
  "slice_name": "Service Dependencies (Circular)",
  "viz_type": "graph_chart",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"source\": \"service_a\", \"target\": \"service_b\", \"metric\": \"count\", \"layout\": \"circular\", \"edgeSymbol\": \"circle,arrow\", \"roam\": \"scale\", \"selectedMode\": \"multiple\", \"color_scheme\": \"d3Category10\"}"
}
```

## Response Format

### Success Response (201 Created)

```json
{
  "id": 123,
  "result": {
    "slice_name": "Microservices Dependency Graph",
    "viz_type": "graph_chart",
    "datasource_id": 42,
    "datasource_type": "table",
    "description": "Force-directed graph showing service dependencies and call volumes",
    "params": "{\"source\": \"calling_service\", \"target\": \"called_service\", \"metric\": {...}, ...}",
    "cache_timeout": 3600,
    "owners": [1],
    "dashboards": [5],
    "changed_on": "2023-10-15T14:30:00",
    "uuid": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"
  }
}
```

## Notes

- Part of the **Flow** category of visualizations in Apache Superset
- Built using [Apache ECharts](https://echarts.apache.org) graph series
- Supports both **directed** and **undirected** graphs via the `edgeSymbol` parameter
- The force-directed layout uses a physics simulation that can take a moment to stabilize
- Node sizes and edge widths are automatically scaled based on the metric values
- If no metric is provided, all edges and nodes will have uniform size/thickness
- Category colors are assigned in the order categories appear in the data
- Force layout parameters (`edgeLength`, `gravity`, `repulsion`, `friction`) only affect force layout mode and are ignored in circular layout
- The `draggable` parameter only works in force layout mode
- Interactive features: zoom, pan (when `roam` is enabled), node selection (when `selectedMode` is enabled), and node dragging (when `draggable` is true in force mode)
- For geospatial relationship data, consider using the deck.gl Arc chart instead
- Tags: Circular, Comparison, Directional, ECharts, Relational, Structural, Transformable, Featured
