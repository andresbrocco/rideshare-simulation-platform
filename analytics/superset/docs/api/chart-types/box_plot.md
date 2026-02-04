# Box Plot (`box_plot`)

## Description
A box and whisker plot visualization that compares the distributions of a related metric across multiple groups. The box in the middle emphasizes the mean, median, and inner 2 quartiles, while the whiskers around each box visualize the min, max, range, and outer 2 quartiles.

## When to Use
Use box plots when you need to visualize the statistical distribution of data across different categories or time periods. This chart type is particularly effective for identifying outliers, comparing distributions, and understanding the spread and central tendency of your data.

## Example Use Cases
- Analyzing salary distributions across different departments in an organization
- Comparing customer response times across multiple service regions
- Monitoring daily temperature variations across different cities or seasons
- Evaluating product quality metrics across manufacturing batches
- Studying test score distributions across different schools or grade levels

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `box_plot` |
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
The `params` field must be a JSON string containing the following parameters:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| columns | array | Yes | Default temporal column | Columns to calculate distribution across. Can include physical columns or adhoc expressions. At least one column is required. |
| time_grain_sqla | string | No | null | Time grain for temporal columns. Only visible when temporal columns are selected. Options: P1D (1 day), P1W (1 week), P1M (1 month), etc. |
| temporal_columns_lookup | object | No | {} | Internal lookup object mapping temporal column names to their temporal status |
| groupby | array | No | [] | Categories to group by on the x-axis. Dimensions contain qualitative values for categorizing data. |
| metrics | array | Yes | - | One or more metrics to display. Each metric can be an aggregation function on a column or custom SQL expression. |
| adhoc_filters | array | No | [] | Filters to apply to the chart query. Can be simple column filters or custom SQL expressions. |
| series_limit | integer | No | null | Limits the number of series displayed. Applied via subquery to limit fetched data. Useful for high cardinality groupings. |
| series_limit_metric | object/string | No | null | Metric used to determine which series to keep when series_limit is applied. Defaults to first metric if undefined. |
| row_limit | integer | No | 10000 | Limits the number of rows computed in the source query. Options: 10, 50, 100, 250, 500, 1000, 5000, 10000, 50000. |
| whiskerOptions | string | No | "Tukey" | Determines how whiskers and outliers are calculated. Options: "Tukey", "Min/max (no outliers)", "2/98 percentiles", "5/95 percentiles", "9/91 percentiles", "10/90 percentiles". |
| x_axis_title | string | No | "" | Title text for the x-axis |
| x_axis_title_margin | integer | No | 0 | Margin for x-axis title. Options: 0, 15, 30, 50, 75, 100, 125, 150, 200. |
| y_axis_title | string | No | "" | Title text for the y-axis |
| y_axis_title_margin | integer | No | 0 | Margin for y-axis title. Options: 0, 15, 30, 50, 75, 100, 125, 150, 200. |
| y_axis_title_position | string | No | "Left" | Position of y-axis title. Options: "Left", "Top". |
| color_scheme | string | No | Default scheme | Color scheme for rendering the chart. Uses categorical color schemes. |
| x_ticks_layout | string | No | "auto" | Layout of ticks on the x-axis. Options: "auto", "flat", "45°", "90°", "staggered". |
| number_format | string | No | "SMART_NUMBER" | D3 format string for formatting numeric values in the chart |
| date_format | string | No | "smart_date" | D3 time format string for formatting date values |
| zoomable | boolean | No | false | Enable data zooming controls for interactive exploration |

### Example Request
```json
{
  "slice_name": "Customer Response Time Distribution by Region",
  "viz_type": "box_plot",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"columns\": [\"order_date\"], \"time_grain_sqla\": \"P1M\", \"groupby\": [\"region\"], \"metrics\": [{\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"response_time_minutes\", \"type\": \"DOUBLE\"}, \"aggregate\": \"AVG\", \"label\": \"Avg Response Time\"}], \"adhoc_filters\": [], \"series_limit\": 10, \"row_limit\": 10000, \"whiskerOptions\": \"Tukey\", \"x_axis_title\": \"Region\", \"y_axis_title\": \"Response Time (minutes)\", \"y_axis_title_position\": \"Left\", \"color_scheme\": \"supersetColors\", \"x_ticks_layout\": \"auto\", \"number_format\": \"SMART_NUMBER\", \"date_format\": \"smart_date\", \"zoomable\": true}",
  "description": "Box plot showing distribution of customer response times across different service regions",
  "owners": [1]
}
```

## Response Format

The API returns a chart object with the following structure:

```json
{
  "id": 123,
  "slice_name": "Customer Response Time Distribution by Region",
  "viz_type": "box_plot",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{...}",
  "description": "Box plot showing distribution of customer response times across different service regions",
  "cache_timeout": null,
  "owners": [1],
  "created_on": "2026-02-03T12:00:00",
  "changed_on": "2026-02-03T12:00:00"
}
```

## Notes

- The `columns` field determines which columns are used to calculate the distribution. When temporal columns are selected, the `time_grain_sqla` control becomes visible.
- The `groupby` field creates separate box plots for each group value on the x-axis.
- The `whiskerOptions` parameter controls the statistical method for calculating whiskers and identifying outliers:
  - **Tukey**: Uses interquartile range (IQR) method, standard for box plots
  - **Min/max (no outliers)**: Whiskers extend to minimum and maximum values
  - **Percentiles**: Various percentile ranges (2/98, 5/95, 9/91, 10/90) for different sensitivity levels
- Metrics must be specified using either saved metric references or adhoc metric objects with aggregation functions.
- The chart uses Apache ECharts library for rendering and supports interactive features like drill-to-detail and drill-by.
