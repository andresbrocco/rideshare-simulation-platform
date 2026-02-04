# Chart Types API Reference

This directory contains comprehensive API documentation for creating charts via the Superset REST API.

## Overview

To create a chart, send a POST request to `/api/v1/chart/` with the appropriate payload. Each chart type (`viz_type`) has specific parameters that control its appearance and behavior.

## Available Chart Types

| Chart Type | viz_type | Documentation |
|------------|----------|---------------|
| AG Grid Table | `ag-grid-table` | [ag-grid-table.md](./ag-grid-table.md) |
| Area Chart | `echarts_area` | [echarts_area.md](./echarts_area.md) |
| Bar Chart | `echarts_timeseries_bar` | [echarts_timeseries_bar.md](./echarts_timeseries_bar.md) |
| Big Number | `big_number` | [big_number.md](./big_number.md) |
| Big Number Period Over Period | `pop_kpi` | [pop_kpi.md](./pop_kpi.md) |
| Big Number Total | `big_number_total` | [big_number_total.md](./big_number_total.md) |
| Box Plot | `box_plot` | [box_plot.md](./box_plot.md) |
| Bubble Chart | `bubble_v2` | [bubble_v2.md](./bubble_v2.md) |
| Bubble Chart (Legacy) | `bubble` | [bubble.md](./bubble.md) |
| Bullet Chart | `bullet` | [bullet.md](./bullet.md) |
| Calendar Heatmap | `cal_heatmap` | [cal_heatmap.md](./cal_heatmap.md) |
| Cartodiagram | `cartodiagram` | [cartodiagram.md](./cartodiagram.md) |
| Chord Diagram | `chord` | [chord.md](./chord.md) |
| Compare Chart | `compare` | [compare.md](./compare.md) |
| Country Map | `country_map` | [country_map.md](./country_map.md) |
| Funnel Chart | `funnel` | [funnel.md](./funnel.md) |
| Gantt Chart | `gantt_chart` | [gantt_chart.md](./gantt_chart.md) |
| Gauge Chart | `gauge_chart` | [gauge_chart.md](./gauge_chart.md) |
| Generic Chart (Timeseries) | `echarts_timeseries` | [echarts_timeseries.md](./echarts_timeseries.md) |
| Graph Chart | `graph_chart` | [graph_chart.md](./graph_chart.md) |
| Handlebars | `handlebars` | [handlebars.md](./handlebars.md) |
| Heatmap | `heatmap_v2` | [heatmap_v2.md](./heatmap_v2.md) |
| Histogram | `histogram_v2` | [histogram_v2.md](./histogram_v2.md) |
| Horizon Chart | `horizon` | [horizon.md](./horizon.md) |
| Line Chart | `echarts_timeseries_line` | [echarts_timeseries_line.md](./echarts_timeseries_line.md) |
| MapBox | `mapbox` | [mapbox.md](./mapbox.md) |
| Mixed Timeseries | `mixed_timeseries` | [mixed_timeseries.md](./mixed_timeseries.md) |
| Paired T-Test | `paired_ttest` | [paired_ttest.md](./paired_ttest.md) |
| Parallel Coordinates | `para` | [para.md](./para.md) |
| Partition Chart | `partition` | [partition.md](./partition.md) |
| Pie Chart | `pie` | [pie.md](./pie.md) |
| Pivot Table | `pivot_table_v2` | [pivot_table_v2.md](./pivot_table_v2.md) |
| Radar Chart | `radar` | [radar.md](./radar.md) |
| Rose Chart | `rose` | [rose.md](./rose.md) |
| Sankey Diagram | `sankey_v2` | [sankey_v2.md](./sankey_v2.md) |
| Scatter Plot | `echarts_timeseries_scatter` | [echarts_timeseries_scatter.md](./echarts_timeseries_scatter.md) |
| Smooth Line Chart | `echarts_timeseries_smooth` | [echarts_timeseries_smooth.md](./echarts_timeseries_smooth.md) |
| Step Line Chart | `echarts_timeseries_step` | [echarts_timeseries_step.md](./echarts_timeseries_step.md) |
| Sunburst Chart | `sunburst_v2` | [sunburst_v2.md](./sunburst_v2.md) |
| Table | `table` | [table.md](./table.md) |
| Time Pivot | `time_pivot` | [time_pivot.md](./time_pivot.md) |
| Time Table | `time_table` | [time_table.md](./time_table.md) |
| Tree Chart | `tree_chart` | [tree_chart.md](./tree_chart.md) |
| Treemap | `treemap_v2` | [treemap_v2.md](./treemap_v2.md) |
| Waterfall Chart | `waterfall` | [waterfall.md](./waterfall.md) |
| Word Cloud | `word_cloud` | [word_cloud.md](./word_cloud.md) |
| World Map | `world_map` | [world_map.md](./world_map.md) |

## Common Request Structure

All chart creation requests share these common fields:

```json
{
  "slice_name": "Chart Name",
  "viz_type": "chart_type_identifier",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{ ... chart-specific JSON ... }",
  "description": "Optional description",
  "owners": [1, 2],
  "cache_timeout": 3600,
  "dashboards": [1]
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `slice_name` | string | Yes | Chart name (max 250 characters) |
| `viz_type` | string | Yes | Chart type identifier from the table above |
| `datasource_id` | integer | Yes | ID of the datasource (dataset) |
| `datasource_type` | string | Yes | Type of datasource (typically `"table"`) |
| `params` | string | Yes | JSON string containing chart-specific parameters |
| `description` | string | No | Optional chart description |
| `owners` | array | No | List of owner user IDs |
| `cache_timeout` | integer | No | Cache timeout in seconds |
| `dashboards` | array | No | List of dashboard IDs to add the chart to |
| `certified_by` | string | No | Name of person who certified the chart |
| `certification_details` | string | No | Details about the certification |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/chart/` | Create a new chart |
| `GET` | `/api/v1/chart/` | List all charts |
| `GET` | `/api/v1/chart/{id}` | Get a specific chart |
| `PUT` | `/api/v1/chart/{id}` | Update a chart |
| `DELETE` | `/api/v1/chart/{id}` | Delete a chart |
| `GET` | `/api/v1/chart/{id}/data/` | Get chart data |

## Chart Categories

Charts are organized into the following categories:

### KPI & Big Numbers
- Big Number (`big_number`)
- Big Number Total (`big_number_total`)
- Big Number Period Over Period (`pop_kpi`)
- Gauge Chart (`gauge_chart`)
- Bullet Chart (`bullet`)

### Time-Series
- Line Chart (`echarts_timeseries_line`)
- Area Chart (`echarts_area`)
- Bar Chart (`echarts_timeseries_bar`)
- Scatter Plot (`echarts_timeseries_scatter`)
- Smooth Line Chart (`echarts_timeseries_smooth`)
- Step Line Chart (`echarts_timeseries_step`)
- Generic Timeseries (`echarts_timeseries`)
- Mixed Timeseries (`mixed_timeseries`)
- Horizon Chart (`horizon`)
- Time Pivot (`time_pivot`)

### Part-to-Whole
- Pie Chart (`pie`)
- Sunburst Chart (`sunburst_v2`)
- Treemap (`treemap_v2`)
- Partition Chart (`partition`)

### Statistical
- Box Plot (`box_plot`)
- Histogram (`histogram_v2`)
- Paired T-Test (`paired_ttest`)
- Bubble Chart (`bubble_v2`)

### Flow & Relationships
- Sankey Diagram (`sankey_v2`)
- Chord Diagram (`chord`)
- Graph Chart (`graph_chart`)
- Funnel Chart (`funnel`)

### Hierarchical
- Tree Chart (`tree_chart`)
- Treemap (`treemap_v2`)
- Sunburst Chart (`sunburst_v2`)
- Partition Chart (`partition`)

### Geographic
- World Map (`world_map`)
- Country Map (`country_map`)
- MapBox (`mapbox`)
- Cartodiagram (`cartodiagram`)

### Tables
- Table (`table`)
- AG Grid Table (`ag-grid-table`)
- Pivot Table (`pivot_table_v2`)
- Time Table (`time_table`)

### Multi-Dimensional
- Radar Chart (`radar`)
- Parallel Coordinates (`para`)
- Heatmap (`heatmap_v2`)
- Calendar Heatmap (`cal_heatmap`)

### Specialized
- Waterfall Chart (`waterfall`)
- Rose Chart (`rose`)
- Gantt Chart (`gantt_chart`)
- Word Cloud (`word_cloud`)
- Handlebars (`handlebars`)
- Compare Chart (`compare`)

See individual chart type documentation for the specific `params` structure and configuration options.
