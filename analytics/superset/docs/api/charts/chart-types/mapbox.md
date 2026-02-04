# MapBox (`mapbox`)

## Description
The MapBox chart visualizes geospatial point data on an interactive map powered by Mapbox GL JS. It displays location data using latitude and longitude coordinates with customizable clustering, point styling, and map themes. Points can be grouped by categories, and clustering automatically aggregates nearby points for better visualization of dense datasets.

## When to Use
Use this chart type when you need to visualize location-based data on an interactive map with clustering capabilities. It is particularly effective for displaying large numbers of geographic points, identifying spatial patterns, and exploring location data across different zoom levels with automatic point aggregation.

## Example Use Cases
- Mapping customer locations with clustering to identify geographic concentration of users
- Visualizing retail store locations with sales metrics shown in cluster labels
- Tracking delivery routes and distribution centers across regions
- Displaying real estate listings with property counts aggregated by neighborhood
- Analyzing event attendance patterns across multiple venue locations
- Monitoring sensor network deployments with real-time data points on a map

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `mapbox` |
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
| all_columns_x | string | Yes | null | Column containing longitude data. Must contain valid longitude values (-180 to 180). |
| all_columns_y | string | Yes | null | Column containing latitude data. Must contain valid latitude values (-90 to 90). |
| clustering_radius | string/integer | No | '60' | The radius (in pixels) the algorithm uses to define a cluster. Valid options: '0', '20', '40', '60', '80', '100', '200', '500', '1000', or custom value. Choose 0 to turn off clustering, but beware that a large number of points (>1000) will cause lag. |
| row_limit | integer | No | 10000 | Maximum number of rows to retrieve from the datasource. |
| adhoc_filters | array | No | [] | List of adhoc filters to apply to the data. Each filter is an object with properties like clause, subject, operator, comparator, and expressionType. |
| groupby | array | No | [] | One or many columns to group by. If grouping, latitude and longitude columns must be present in the groupby. Used to aggregate data points. |
| point_radius | string | No | 'Auto' | The radius of individual points (ones that are not in a cluster). Either a numerical column name or 'Auto', which scales the point based on the largest cluster. Can be set to a column name to vary point size by a metric. |
| point_radius_unit | string | No | 'Pixels' | The unit of measure for the specified point radius. Valid options: 'Pixels', 'Miles', 'Kilometers'. |
| mapbox_label | array | No | [] | Columns to use for labeling clusters and points. 'count' is COUNT(*) if a group by is used. Numerical columns will be aggregated with the aggregator. Non-numerical columns will be used to label points. Leave empty to get a count of points in each cluster. |
| pandas_aggfunc | string | No | 'sum' | Aggregate function applied to the list of points in each cluster to produce the cluster label. Valid options: 'sum', 'mean', 'min', 'max', 'std', 'var'. |
| render_while_dragging | boolean | No | true | Points and clusters will update as the viewport is being changed. Disabling can improve performance on slower devices. |
| mapbox_style | string | No | 'mapbox://styles/mapbox/light-v9' | Base layer map style. Valid options: 'mapbox://styles/mapbox/streets-v9', 'mapbox://styles/mapbox/dark-v9', 'mapbox://styles/mapbox/light-v9', 'mapbox://styles/mapbox/satellite-streets-v9', 'mapbox://styles/mapbox/satellite-v9', 'mapbox://styles/mapbox/outdoors-v9', or custom Mapbox style URL. See Mapbox documentation: https://docs.mapbox.com/help/glossary/style-url/ |
| global_opacity | number | No | 1 | Opacity of all clusters, points, and labels. Must be between 0 and 1. |
| mapbox_color | string | No | 'rgb(0, 139, 139)' | The color for points and clusters in RGB format. Valid preset options: 'rgb(0, 139, 139)' (Dark Cyan), 'rgb(128, 0, 128)' (Purple), 'rgb(255, 215, 0)' (Gold), 'rgb(69, 69, 69)' (Dim Gray), 'rgb(220, 20, 60)' (Crimson), 'rgb(34, 139, 34)' (Forest Green), or custom RGB string. |
| viewport_longitude | number | No | -122.405293 | Longitude of default viewport. Accepts decimal degrees with up to 8 decimal places. |
| viewport_latitude | number | No | 37.772123 | Latitude of default viewport. Accepts decimal degrees with up to 8 decimal places. |
| viewport_zoom | number | No | 11 | Zoom level of the map. Higher values zoom in closer. Accepts decimal values for precise zoom levels. |

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
  "slice_name": "Customer Distribution Map",
  "viz_type": "mapbox",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"all_columns_x\": \"longitude\", \"all_columns_y\": \"latitude\", \"clustering_radius\": \"60\", \"row_limit\": 5000, \"adhoc_filters\": [{\"clause\": \"WHERE\", \"subject\": \"signup_date\", \"operator\": \"TEMPORAL_RANGE\", \"comparator\": \"Last year\", \"expressionType\": \"SIMPLE\"}], \"groupby\": [], \"point_radius\": \"Auto\", \"point_radius_unit\": \"Pixels\", \"mapbox_label\": [\"customer_type\", \"total_purchases\"], \"pandas_aggfunc\": \"sum\", \"render_while_dragging\": true, \"mapbox_style\": \"mapbox://styles/mapbox/light-v9\", \"global_opacity\": 0.8, \"mapbox_color\": \"rgb(0, 139, 139)\", \"viewport_longitude\": -122.405293, \"viewport_latitude\": 37.772123, \"viewport_zoom\": 11}",
  "description": "Interactive map showing customer locations with clustering",
  "owners": [1]
}
```

## Notes
- This chart type is marked as **Legacy** and uses the Mapbox GL JS library
- A Mapbox API token is required in your Superset configuration to use this visualization
- The `all_columns_x` (longitude) and `all_columns_y` (latitude) fields are required
- Clustering is enabled by default with a 60-pixel radius; set to 0 to disable
- For datasets with more than 1000 points, clustering is strongly recommended to avoid performance issues
- When using `groupby`, ensure latitude and longitude columns are included
- The `point_radius` can be set to a column name to make point size data-driven
- Viewport settings (longitude, latitude, zoom) control the initial map view but don't affect data queries
- Custom Mapbox styles can be used by providing a valid Mapbox style URL
- The map supports interactive panning and zooming; viewport changes don't trigger data refresh when `render_while_dragging` is disabled
- Color must be specified in RGB format: `rgb(red, green, blue)` where values are 0-255
