# Gantt Chart (`gantt_chart`)

## Description
Gantt charts visualize important events over a time span, where each event is displayed as a horizontal bar along a timeline. Every data point is represented as a separate event with a start time, end time, and optional grouping dimensions, making it ideal for tracking tasks, processes, or events across time.

## When to Use
Use Gantt charts when you need to show temporal events, durations, or activities with clear start and end times. They are particularly effective for visualizing timelines, schedules, or any data where both the timing and duration of events are important to understand.

## Example Use Cases
- Project management timelines showing task durations and dependencies
- Resource allocation and capacity planning over time
- Manufacturing process timelines tracking production stages
- Event scheduling and conference room bookings
- Service level agreement (SLA) monitoring with incident durations
- Equipment maintenance schedules and downtime tracking

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `gantt_chart` |
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

The `params` field must be a JSON string containing the following properties:

#### Query Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| start_time | object | Yes | null | Temporal column representing the start time of each event. Must be a column reference with `type_generic: "TEMPORAL"`. |
| end_time | object | Yes | null | Temporal column representing the end time of each event. Must be a column reference with `type_generic: "TEMPORAL"`. |
| y_axis | object | No | null | Dimension to use on y-axis. Defines the categories or entities shown vertically. |
| series | object | No | null | Dimension for grouping entities. Each series is represented by a specific color in the chart. When specified, creates visual groups of events. |
| subcategories | boolean | No | false | Divides each category into subcategories based on the values in the series dimension. Can be used to exclude intersections. Only visible when `series` is defined. |
| tooltip_metrics | array | No | [] | Additional metrics to show in the tooltip when hovering over events. |
| tooltip_columns | array | No | [] | Additional columns to show in the tooltip when hovering over events. |
| adhoc_filters | array | No | [] | Ad-hoc filters to apply to the query. Each filter has a clause, expressionType, operator, subject, and comparator. |
| order_by_cols | array | No | [] | Order results by selected columns. Format: `["[\"column_name\", true]"]` where true=ascending, false=descending. |
| row_limit | integer | No | 10000 | Maximum number of rows to retrieve from the datasource. |

#### Chart Title Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis_title | string | No | "" | Title for the X axis |
| x_axis_title_margin | integer | No | 0 | Margin for X axis title (options: 0, 15, 30, 50, 75, 100, 125, 150, 200) |
| y_axis_title | string | No | "" | Title for the Y axis |
| y_axis_title_margin | integer | No | 0 | Margin for Y axis title (options: 0, 15, 30, 50, 75, 100, 125, 150, 200) |
| y_axis_title_position | string | No | "Left" | Position of Y axis title. Options: "Left", "Top" |

#### Chart Options

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| color_scheme | string | No | "supersetColors" | Color scheme for rendering the chart. Uses categorical color schemes from the registry. |
| show_legend | boolean | No | true | Whether to display a legend for the chart |
| legendType | string | No | "scroll" | Legend type. Options: "scroll", "plain" |
| legendOrientation | string | No | "top" | Legend orientation. Options: "top", "bottom", "left", "right" |
| legendMargin | integer | No | null | Additional padding for legend (in pixels) |
| legendSort | string | No | null | Sort legend items. Options: "asc" (label ascending), "desc" (label descending), null (sort by data) |
| zoomable | boolean | No | false | Enable data zooming controls for panning and zooming the time axis |
| show_extra_controls | boolean | No | false | Show additional chart customization controls |

#### X Axis Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| x_axis_time_bounds | object | No | null | Bounds for the X-axis timeline. Selected time merges with min/max date of the data. When left empty, bounds are dynamically defined based on the min/max of the data. |
| x_axis_time_format | string | No | "smart_date" | Time format for X axis labels. Uses D3 time format strings (e.g., "%Y-%m-%d", "%H:%M:%S", "smart_date"). |

#### Tooltip Parameters

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| tooltipTimeFormat | string | No | "smart_date" | Time format for dates shown in tooltip. Uses D3 time format strings. |
| tooltipValuesFormat | string | No | "SMART_NUMBER" | Number format for metric values in tooltip. Uses D3 format strings (e.g., ",.2f", ".1%", "SMART_NUMBER"). |

### Example Request

```json
{
  "slice_name": "Project Timeline",
  "viz_type": "gantt_chart",
  "datasource_id": 42,
  "datasource_type": "table",
  "description": "Timeline of project tasks and milestones",
  "owners": [1],
  "params": "{\"start_time\": {\"column_name\": \"task_start_date\", \"type_generic\": \"TEMPORAL\"}, \"end_time\": {\"column_name\": \"task_end_date\", \"type_generic\": \"TEMPORAL\"}, \"y_axis\": {\"column_name\": \"task_name\"}, \"series\": {\"column_name\": \"project_phase\"}, \"subcategories\": false, \"tooltip_metrics\": [], \"tooltip_columns\": [{\"column_name\": \"assigned_to\"}], \"adhoc_filters\": [{\"clause\": \"WHERE\", \"expressionType\": \"SIMPLE\", \"operator\": \"IN\", \"subject\": \"status\", \"comparator\": [\"In Progress\", \"Completed\"]}], \"order_by_cols\": [\"[\\\"task_start_date\\\", true]\"], \"row_limit\": 100, \"color_scheme\": \"supersetColors\", \"show_legend\": true, \"legendType\": \"scroll\", \"legendOrientation\": \"top\", \"legendMargin\": 15, \"legendSort\": null, \"zoomable\": true, \"show_extra_controls\": false, \"x_axis_time_format\": \"%Y-%m-%d\", \"x_axis_title\": \"Timeline\", \"x_axis_title_margin\": 30, \"y_axis_title\": \"Tasks\", \"y_axis_title_margin\": 50, \"y_axis_title_position\": \"Left\", \"tooltipTimeFormat\": \"smart_date\", \"tooltipValuesFormat\": \"SMART_NUMBER\"}",
  "cache_timeout": 3600,
  "dashboards": [5]
}
```

### Example Request (Minimal)

```json
{
  "slice_name": "Simple Task Timeline",
  "viz_type": "gantt_chart",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"start_time\": {\"column_name\": \"start_date\", \"type_generic\": \"TEMPORAL\"}, \"end_time\": {\"column_name\": \"end_date\", \"type_generic\": \"TEMPORAL\"}, \"y_axis\": {\"column_name\": \"task_name\"}}"
}
```

## Notes

- **Temporal Columns Required**: Both `start_time` and `end_time` must reference columns with temporal data types (dates or timestamps).
- **Y-Axis Dimension**: The `y_axis` field defines what appears on the vertical axis. Each unique value creates a separate row in the Gantt chart.
- **Series Grouping**: When `series` is defined, events are grouped and color-coded by the series dimension, creating visual distinction between different categories.
- **Subcategories**: Enable `subcategories` to prevent overlapping events in the same category by creating sub-rows based on the series dimension.
- **Zoom Capability**: Enable `zoomable` to allow users to interactively pan and zoom the timeline, useful for charts with large time spans.
- **Time Bounds**: Use `x_axis_time_bounds` to set a fixed time range for the X-axis, regardless of the data's actual time span.
- **Legend Visibility**: The legend controls (type, orientation, margin, sort) are only visible when `show_legend` is true.
- **Format Strings**: Both time and number formats use D3 format strings. Use "smart_date" and "SMART_NUMBER" for automatic formatting.
