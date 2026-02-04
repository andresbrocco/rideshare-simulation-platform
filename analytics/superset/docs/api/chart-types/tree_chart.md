# Tree Chart (`tree_chart`)

## Description
A Tree Chart visualizes hierarchical data structures using a familiar tree-like layout, showing parent-child relationships between nodes. The chart supports both orthogonal (rectangular) and radial (circular) layouts, with customizable node symbols, labels, and interactive features. Nodes can be sized based on metric values, and the tree can be configured to show different levels of depth. This chart is ideal for displaying organizational structures, file systems, taxonomies, and any data with clear parent-child relationships.

## When to Use
Use a Tree Chart when you need to visualize hierarchical data with a clear parent-child relationship structure. This chart is particularly effective for showing organizational hierarchies, category taxonomies, file system structures, and any data that has a single root node with branching relationships.

## Example Use Cases
- Visualizing organizational charts and reporting structures
- Displaying file system hierarchies and directory structures
- Mapping category taxonomies and classification systems
- Showing decision tree structures and flowcharts
- Analyzing family trees and genealogical relationships
- Displaying product category hierarchies in e-commerce systems

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `tree_chart` |
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
| id | string | Yes | - | Name of the column containing the node ID |
| parent | string | Yes | - | Name of the column containing the parent node ID |
| name | string | No | - | Optional name of the data column for node labels |
| root_node_id | string | No | - | ID of the root node of the tree. If not specified, the chart will attempt to find the root automatically. |
| metric | object/string | No | - | Metric for node values. Can be an adhoc metric object or a saved metric name. Used to size nodes or display values. |
| adhoc_filters | array | No | [] | List of adhoc filter objects for filtering the data |
| row_limit | integer | No | 10000 | Maximum number of rows to compute in the query (can be up to SQL_MAX_ROW configuration) |
| layout | string | No | "orthogonal" | Tree layout type. Options: "orthogonal" (rectangular tree), "radial" (circular tree) |
| orient | string | No | "LR" | Tree orientation. Options: "LR" (left to right), "RL" (right to left), "TB" (top to bottom), "BT" (bottom to top). Only applicable when layout is "orthogonal". |
| node_label_position | string | No | "left" | Position of intermediate node labels on tree. Options: "left", "top", "right", "bottom" |
| child_label_position | string | No | "bottom" | Position of child node (leaf) labels on tree. Options: "left", "top", "right", "bottom" |
| emphasis | string | No | "descendant" | Which relatives to highlight on hover. Options: "ancestor" (highlight path to root), "descendant" (highlight children). Only applicable when layout is "orthogonal". |
| symbol | string | No | "emptyCircle" | Symbol shape for tree nodes. Options: "emptyCircle", "circle", "rect", "triangle", "diamond", "pin", "arrow", "none" |
| symbolSize | number | No | 7 | Size of node symbols (range: 5-30, step: 2) |
| roam | boolean/string | No | true | Enable graph roaming. Options: false (disabled), "scale" (scale only), "move" (move only), true (scale and move) |
| initialTreeDepth | integer | No | 2 | The initial level (depth) of the tree to display. If set to -1, all nodes are expanded. (range: -1 to 10) |

#### Field Details

**id**
- Required field specifying the column containing unique node identifiers
- Each row should have a unique ID value
- Example: `"node_id"` or `"employee_id"`

**parent**
- Required field specifying the column containing the parent node ID for each node
- Root nodes should have a null or special parent value
- Creates the parent-child relationship that forms the tree structure
- Example: `"parent_node_id"` or `"manager_id"`

**name**
- Optional column for node labels
- If not specified, the ID value will be used as the label
- Useful when you want to display friendly names instead of IDs
- Example: `"employee_name"` or `"category_name"`

**root_node_id**
- Optional specification of which node should be the root of the tree
- If not provided, the chart will automatically detect the root node (node with no parent)
- Useful when you want to display a subtree starting from a specific node
- Example: `"ROOT"` or `"1"`

**metric**
- Defines values associated with each node
- Can be an adhoc metric object with aggregation function:
  ```json
  {
    "expressionType": "SIMPLE",
    "column": {
      "column_name": "employee_count",
      "type": "BIGINT"
    },
    "aggregate": "SUM",
    "label": "Total Employees"
  }
  ```
- Or a string referencing a saved metric: `"count"`
- Metric values can be used to size nodes or display in tooltips

**layout**
- `"orthogonal"`: Traditional rectangular tree layout with straight lines between nodes. Supports multiple orientations.
- `"radial"`: Circular/radial layout where nodes are arranged in concentric circles emanating from the center root node.

**orient**
- Only applicable when `layout` is `"orthogonal"`
- Controls the direction of tree growth:
  - `"LR"`: Left to Right (root on left, children expand right)
  - `"RL"`: Right to Left (root on right, children expand left)
  - `"TB"`: Top to Bottom (root on top, children expand downward)
  - `"BT"`: Bottom to Top (root on bottom, children expand upward)

**node_label_position / child_label_position**
- Control where labels appear relative to nodes
- `node_label_position`: Position for intermediate nodes (nodes with children)
- `child_label_position`: Position for leaf nodes (nodes without children)
- Options: `"left"`, `"top"`, `"right"`, `"bottom"`
- Helps prevent label overlap and improves readability

**emphasis**
- Only applicable when `layout` is `"orthogonal"`
- Controls which related nodes are highlighted when hovering over a node:
  - `"ancestor"`: Highlights the path from the hovered node up to the root
  - `"descendant"`: Highlights all children and descendants of the hovered node
- Useful for tracing relationships in complex trees

**symbol**
- Defines the visual shape of tree nodes
- Options include:
  - `"emptyCircle"`: Hollow circle (default)
  - `"circle"`: Filled circle
  - `"rect"`: Rectangle
  - `"triangle"`: Triangle
  - `"diamond"`: Diamond shape
  - `"pin"`: Pin/marker shape
  - `"arrow"`: Arrow shape
  - `"none"`: No symbol (labels only)

**symbolSize**
- Controls the size of node symbols in pixels
- Range: 5 to 30 (increments of 2)
- Larger values make nodes more prominent but may cause overlap in dense trees

**roam**
- Controls user interaction with the tree viewport
- `false`: No zooming or panning allowed
- `"scale"`: Only zooming allowed
- `"move"`: Only panning allowed
- `true`: Both zooming and panning allowed (default)
- Useful for exploring large trees

**initialTreeDepth**
- Controls how many levels of the tree are initially visible
- Range: -1 to 10
- `-1`: All nodes expanded (full tree visible)
- `0`: Only root node visible
- `1`: Root and first level children visible
- `2`: Root, first level, and second level visible (default)
- Higher values show more of the tree initially but may clutter the view for large trees

**adhoc_filters**
- Array of filter objects to apply to the data before building the tree
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
- Useful for filtering to show only active nodes or specific subtrees

### Example Request

```json
{
  "slice_name": "Corporate Organization Chart",
  "viz_type": "tree_chart",
  "datasource_id": 42,
  "datasource_type": "table",
  "description": "Hierarchical view of company organizational structure",
  "params": "{\"id\": \"employee_id\", \"parent\": \"manager_id\", \"name\": \"employee_name\", \"root_node_id\": \"CEO_001\", \"metric\": {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"team_size\", \"type\": \"INTEGER\"}, \"aggregate\": \"SUM\", \"label\": \"Team Size\"}, \"adhoc_filters\": [{\"expressionType\": \"SIMPLE\", \"clause\": \"WHERE\", \"subject\": \"status\", \"operator\": \"==\", \"comparator\": \"active\"}], \"row_limit\": 10000, \"layout\": \"orthogonal\", \"orient\": \"TB\", \"node_label_position\": \"right\", \"child_label_position\": \"bottom\", \"emphasis\": \"descendant\", \"symbol\": \"emptyCircle\", \"symbolSize\": 7, \"roam\": true, \"initialTreeDepth\": 2}",
  "cache_timeout": 3600,
  "owners": [1],
  "dashboards": [5]
}
```

### Minimal Example Request

```json
{
  "slice_name": "Basic Hierarchy Tree",
  "viz_type": "tree_chart",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"id\": \"node_id\", \"parent\": \"parent_id\"}"
}
```

### Radial Layout Example Request

```json
{
  "slice_name": "Category Taxonomy (Radial)",
  "viz_type": "tree_chart",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"id\": \"category_id\", \"parent\": \"parent_category_id\", \"name\": \"category_name\", \"layout\": \"radial\", \"symbol\": \"circle\", \"symbolSize\": 9, \"node_label_position\": \"right\", \"child_label_position\": \"right\", \"roam\": \"scale\", \"initialTreeDepth\": 3}"
}
```

### Full Configuration Example Request

```json
{
  "slice_name": "File System Explorer",
  "viz_type": "tree_chart",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"id\": \"path\", \"parent\": \"parent_path\", \"name\": \"file_name\", \"root_node_id\": \"/\", \"metric\": \"file_size_mb\", \"adhoc_filters\": [{\"expressionType\": \"SIMPLE\", \"clause\": \"WHERE\", \"subject\": \"file_type\", \"operator\": \"!=\", \"comparator\": \"hidden\"}], \"row_limit\": 5000, \"layout\": \"orthogonal\", \"orient\": \"LR\", \"node_label_position\": \"left\", \"child_label_position\": \"bottom\", \"emphasis\": \"ancestor\", \"symbol\": \"rect\", \"symbolSize\": 11, \"roam\": true, \"initialTreeDepth\": -1}"
}
```

## Response Format

### Success Response (201 Created)

```json
{
  "id": 123,
  "result": {
    "slice_name": "Corporate Organization Chart",
    "viz_type": "tree_chart",
    "datasource_id": 42,
    "datasource_type": "table",
    "description": "Hierarchical view of company organizational structure",
    "params": "{\"id\": \"employee_id\", \"parent\": \"manager_id\", \"name\": \"employee_name\", ...}",
    "cache_timeout": 3600,
    "owners": [1],
    "dashboards": [5],
    "changed_on": "2023-10-15T14:30:00",
    "uuid": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"
  }
}
```

## Notes

- Part of the **Part of a Whole** category of visualizations in Apache Superset
- Built using [Apache ECharts](https://echarts.apache.org) tree series
- Supports both **orthogonal** (rectangular) and **radial** (circular) tree layouts
- The data must have a clear parent-child relationship defined by the `id` and `parent` columns
- Each node must have a unique ID, and parent IDs must reference valid node IDs (except for the root)
- The root node is identified as the node whose parent ID is null, empty, or doesn't exist in the ID column
- If multiple root nodes are detected, only the first one will be used as the tree root
- The `orient` and `emphasis` parameters only affect orthogonal layout and are ignored in radial layout
- Interactive features: zoom and pan (when `roam` is enabled), expand/collapse nodes by clicking
- The `initialTreeDepth` setting controls the initial view but users can manually expand/collapse nodes
- For large trees (500+ nodes), consider using a higher `initialTreeDepth` value like 1 or 2 to improve initial render performance
- Node sizes can be scaled based on metric values to show quantitative information
- The `name` field is optional; if not provided, the `id` value will be displayed as the node label
- For visualizing network relationships without strict parent-child hierarchy, consider using the Graph Chart instead
- For showing part-to-whole relationships with emphasis on proportions, consider using Sunburst or Treemap charts
- Tags: Categorical, ECharts, Multi-Levels, Relational, Structural, Featured
