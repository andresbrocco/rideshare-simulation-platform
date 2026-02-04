# Cartodiagram (`cartodiagram`)

## Description
The Cartodiagram visualization displays existing Superset charts on an interactive map. This plugin takes any other chart type (pie charts, line charts, bar charts, etc.) and places them at geographic locations specified by a geometry column. Each chart appears at its corresponding location, allowing users to visualize data patterns across geographic space while maintaining the full functionality and configuration options of the underlying chart type.

## When to Use
Use this chart type when you need to display detailed chart visualizations at specific geographic locations on a map. It is particularly effective for combining spatial and statistical analysis, allowing viewers to see both the geographic distribution and detailed chart data for each location simultaneously.

## Example Use Cases
- Display pie charts showing product mix at different retail store locations
- Show time-series line charts of temperature or pollution levels at monitoring stations
- Visualize sales performance bar charts at regional office locations
- Display gauge charts for operational metrics at factory locations
- Show multiple metrics via small multiples charts distributed geographically
- Combine spatial distribution with detailed statistical breakdowns

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `cartodiagram` |
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
The `params` field must be a JSON string containing the following fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| selected_chart | string | Yes | null | JSON string containing the chart configuration to display on the map. Must include `viz_type` (chart type) and `params` (chart-specific configuration). |
| geom_column | string | Yes | null | Name of the column containing geometry data. Must be a GeoJSON Point Geometry string in WGS 84/Pseudo-Mercator (EPSG:3857) format. |
| layer_configs | array | No | [] | Array of background map layer configurations. Each layer can be WMS, WFS, or XYZ type. See Layer Configuration section below. |
| map_view | object | No | `{"mode": "FIT_DATA"}` | Configuration for the initial map extent. Can be "FIT_DATA" (automatically fits all data points) or "CUSTOM" (user-defined extent with zoom, latitude, longitude). |
| chart_background_color | object | No | `{"r": 255, "g": 255, "b": 255, "a": 0.2}` | RGBA color object for chart background. Values: r, g, b (0-255), a (0-1). |
| chart_background_border_radius | integer | No | 10 | Corner radius of chart backgrounds in pixels (0-100). |
| chart_size | object | No | See Chart Size Configuration | Configuration object defining how chart sizes vary by map zoom level. See Chart Size Configuration section below. |

#### selected_chart Format
The `selected_chart` field must be a JSON string containing:
```json
{
  "viz_type": "pie" | "bar" | "line" | "echarts_timeseries_line" | etc.,
  "params": "{...chart-specific configuration...}"
}
```

The chart specified in `selected_chart` must:
- Be from the same datasource as the cartodiagram
- Have valid configuration for its chart type
- The `groupby` parameter will be automatically modified to include the geometry column as the first grouping dimension

#### Layer Configuration
Each layer in `layer_configs` must be one of three types:

**XYZ Layer (Tile Layer)**
```json
{
  "type": "XYZ",
  "title": "Layer Display Name",
  "url": "https://example.com/tiles/{z}/{x}/{y}.png",
  "attribution": "Map data attribution text"
}
```

**WMS Layer (Web Map Service)**
```json
{
  "type": "WMS",
  "title": "Layer Display Name",
  "url": "https://example.com/wms",
  "version": "1.3.0",
  "layersParam": "layer_name",
  "attribution": "Map data attribution text"
}
```

**WFS Layer (Web Feature Service)**
```json
{
  "type": "WFS",
  "title": "Layer Display Name",
  "url": "https://example.com/wfs",
  "version": "2.0.0",
  "typeName": "feature_type_name",
  "maxFeatures": 1000,
  "style": { /* GeoStyler style object */ },
  "attribution": "Map data attribution text"
}
```

#### Map View Configuration
The `map_view` object controls the initial map extent:

**Fit Data Mode (Default)**
```json
{
  "mode": "FIT_DATA"
}
```
Automatically adjusts the map extent to include all data points.

**Custom Mode**
```json
{
  "mode": "CUSTOM",
  "zoom": 10,
  "latitude": 40.7128,
  "longitude": -74.0060,
  "fixedZoom": 10,
  "fixedLatitude": 40.7128,
  "fixedLongitude": -74.0060
}
```

#### Chart Size Configuration
The `chart_size` object controls how chart dimensions vary with map zoom levels. Three configuration types are available:

**Fixed Size (Same size at all zoom levels)**
```json
{
  "type": "FIXED",
  "configs": {
    "zoom": 6,
    "width": 100,
    "height": 100
  },
  "values": {
    "0": {"width": 100, "height": 100},
    "1": {"width": 100, "height": 100},
    ...
    "28": {"width": 100, "height": 100}
  }
}
```

**Linear Scaling (Size increases linearly with zoom)**
```json
{
  "type": "LINEAR",
  "configs": {
    "zoom": 6,
    "width": 100,
    "height": 100,
    "slope": 30
  },
  "values": {
    /* Computed values for zoom levels 0-28 */
  }
}
```
Chart size increases by `slope` pixels per zoom level.

**Exponential Scaling (Size increases exponentially with zoom)**
```json
{
  "type": "EXP",
  "configs": {
    "zoom": 6,
    "width": 100,
    "height": 100,
    "exponent": 2
  },
  "values": {
    /* Computed values for zoom levels 0-28 */
  }
}
```
Chart size increases exponentially based on the `exponent` value.

Note: Zoom levels range from 0 (world view) to 28 (maximum detail). The `values` object must contain width/height pairs for each zoom level if manually specified.

### Example Request
```json
{
  "slice_name": "Store Performance Maps",
  "viz_type": "cartodiagram",
  "datasource_id": 123,
  "datasource_type": "table",
  "params": "{\"selected_chart\":\"{\\\"viz_type\\\":\\\"pie\\\",\\\"params\\\":\\\"{\\\\\\\"groupby\\\\\\\":[\\\\\\\"product_category\\\\\\\"],\\\\\\\"metric\\\\\\\":\\\\\\\"sales_amount\\\\\\\",\\\\\\\"color_scheme\\\\\\\":\\\\\\\"supersetColors\\\\\\\",\\\\\\\"donut\\\\\\\":false,\\\\\\\"show_labels\\\\\\\":true}\\\"}\",\"geom_column\":\"store_location\",\"layer_configs\":[{\"type\":\"XYZ\",\"title\":\"OpenStreetMap\",\"url\":\"https://tile.openstreetmap.org/{z}/{x}/{y}.png\",\"attribution\":\"© OpenStreetMap contributors\"}],\"map_view\":{\"mode\":\"FIT_DATA\"},\"chart_background_color\":{\"r\":255,\"g\":255,\"b\":255,\"a\":0.2},\"chart_background_border_radius\":10,\"chart_size\":{\"type\":\"LINEAR\",\"configs\":{\"zoom\":6,\"width\":100,\"height\":100,\"slope\":30},\"values\":{}}}",
  "description": "Interactive map showing pie charts of product sales at each store location",
  "cache_timeout": 3600,
  "dashboards": [456],
  "owners": [789]
}
```

### Example params Object (before JSON stringification)
```json
{
  "selected_chart": "{\"viz_type\":\"pie\",\"params\":\"{\\\"groupby\\\":[\\\"product_category\\\"],\\\"metric\\\":\\\"sales_amount\\\",\\\"color_scheme\\\":\\\"supersetColors\\\",\\\"donut\\\":false,\\\"show_labels\\\":true}\"}",
  "geom_column": "store_location",
  "layer_configs": [
    {
      "type": "XYZ",
      "title": "OpenStreetMap",
      "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      "attribution": "© OpenStreetMap contributors"
    }
  ],
  "map_view": {
    "mode": "FIT_DATA"
  },
  "chart_background_color": {
    "r": 255,
    "g": 255,
    "b": 255,
    "a": 0.2
  },
  "chart_background_border_radius": 10,
  "chart_size": {
    "type": "LINEAR",
    "configs": {
      "zoom": 6,
      "width": 100,
      "height": 100,
      "slope": 30
    },
    "values": {}
  }
}
```

### Simplified Example with Basic Configuration
```json
{
  "selected_chart": "{\"viz_type\":\"bar\",\"params\":\"{\\\"metrics\\\":[\\\"count\\\"],\\\"groupby\\\":[\\\"category\\\"]}\"}",
  "geom_column": "location_point",
  "layer_configs": [
    {
      "type": "XYZ",
      "title": "Base Map",
      "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    }
  ],
  "map_view": {
    "mode": "FIT_DATA"
  }
}
```

## Notes
- The geometry column must contain valid GeoJSON Point Geometry strings in WGS 84/Pseudo-Mercator (EPSG:3857) projection
- The selected chart must be created from the same datasource as the cartodiagram
- All configuration options from the underlying chart type are supported
- The `groupby` parameter of the selected chart will be automatically modified to include the geometry column as the first dimension
- Dashboard filters applied to the cartodiagram will also be applied to the charts displayed on the map
- By default, Superset rejects requests to third-party domains. To include map layers from external sources, adjust the CSP (Content Security Policy) settings in your Superset configuration
- This chart type is marked as 'Experimental' and may have evolving features
- The chart uses interactive OpenLayers maps with support for panning, zooming, and layer toggling
- Multiple background layers can be stacked, with the order determined by their position in the `layer_configs` array
- Chart rendering performance may be affected when displaying a large number of locations or complex charts
