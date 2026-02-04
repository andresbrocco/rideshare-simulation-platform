# Radar Chart (`radar`)

## Description
The Radar Chart (also known as Spider Chart or Star Chart) is a multivariate visualization that displays multiple quantitative variables on axes starting from the same point. Each axis represents a different metric, and data points are plotted on each axis and connected to form a polygon shape. This visualization is particularly effective for comparing multiple entities across several dimensions simultaneously, making it easy to identify patterns, outliers, and relative strengths and weaknesses.

## When to Use
Radar charts are ideal when you need to compare multiple entities across several metrics or dimensions. They excel at showing multivariate observations and making it easy to spot similarities and differences between groups. The circular layout provides an intuitive way to see which metrics are performing better or worse for each category, and the polygon shapes make it easy to identify patterns and outliers at a glance.

## Example Use Cases
- Comparing product performance across multiple criteria (price, quality, durability, customer satisfaction, market share)
- Evaluating employee skills across different competencies (technical skills, communication, leadership, problem-solving)
- Analyzing sports team statistics across various metrics (offense, defense, speed, teamwork, stamina)
- Assessing software quality across multiple dimensions (performance, security, usability, maintainability, scalability)
- Comparing competitor strengths and weaknesses across market factors (innovation, customer service, pricing, brand recognition, distribution)

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `radar` |
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
| groupby | array | Yes | [] | List of columns to group by. Each unique value creates a separate radar polygon/series |
| metrics | array | Yes | [] | List of metrics to display. Each metric becomes an axis on the radar chart. Can be strings (datasource metric names) or ad-hoc metric objects |
| adhoc_filters | array | No | [] | List of ad-hoc filter objects to apply to the query |
| row_limit | integer | No | 10 | Maximum number of rows/series to retrieve from datasource |
| timeseries_limit_metric | object/string | No | null | Metric used to determine which series to keep when row_limit is applied. Limits the number of series by sorting by this metric |
| color_scheme | string | No | 'supersetColors' | Color scheme to use for the chart |
| show_labels | boolean | No | true | Whether to display labels on the chart data points |
| label_type | string | No | 'value' | What should be shown on the label. Options: 'value' (show metric value), 'key_value' (show category and value) |
| label_position | string | No | 'top' | Position of the label relative to data point. Options: 'top', 'left', 'right', 'bottom', 'inside', 'insideLeft', 'insideRight', 'insideTop', 'insideBottom', 'insideTopLeft', 'insideBottomLeft', 'insideTopRight', 'insideBottomRight' |
| number_format | string | No | 'SMART_NUMBER' | Number format for metric values (e.g., 'SMART_NUMBER', '.2f', '$,.2f', ',d') |
| date_format | string | No | 'smart_date' | Date format string for temporal values |
| is_circle | boolean | No | false | Radar render type, whether to display 'circle' shape instead of polygon |
| column_config | object | No | {} | Configuration for customizing individual metrics. Keys are metric names, values are objects with `radarMetricMaxValue` and `radarMetricMinValue` properties |
| show_legend | boolean | No | true | Whether to display a legend for the chart |
| legendType | string | No | 'scroll' | Legend type. Options: 'scroll', 'plain' |
| legendOrientation | string | No | 'top' | Legend position. Options: 'top', 'bottom', 'left', 'right' |
| legendMargin | integer | No | null | Additional padding for legend in pixels |
| legendSort | string | No | null | Sort legend items. Options: 'asc' (label ascending), 'desc' (label descending), null (sort by data) |

#### column_config Details
The `column_config` object allows you to customize the min/max values for individual metrics:

```json
{
  "metric_name": {
    "radarMetricMaxValue": 100,
    "radarMetricMinValue": 0
  }
}
```

- **radarMetricMaxValue**: Optional maximum value for this metric's axis. If not set, it will be automatically calculated from the data
- **radarMetricMinValue**: Optional minimum value for this metric's axis. Defaults to 0 if not set

### Example Request
```json
{
  "slice_name": "Product Performance Comparison",
  "viz_type": "radar",
  "datasource_id": 1,
  "datasource_type": "table",
  "params": "{\"groupby\":[\"product_name\"],\"metrics\":[\"avg_quality_score\",\"avg_price_score\",\"avg_durability_score\",\"avg_customer_satisfaction\",\"avg_market_share\"],\"row_limit\":5,\"color_scheme\":\"supersetColors\",\"show_labels\":true,\"label_type\":\"value\",\"label_position\":\"top\",\"number_format\":\"SMART_NUMBER\",\"date_format\":\"smart_date\",\"is_circle\":false,\"column_config\":{\"avg_quality_score\":{\"radarMetricMaxValue\":100,\"radarMetricMinValue\":0},\"avg_price_score\":{\"radarMetricMaxValue\":100,\"radarMetricMinValue\":0},\"avg_durability_score\":{\"radarMetricMaxValue\":100,\"radarMetricMinValue\":0},\"avg_customer_satisfaction\":{\"radarMetricMaxValue\":100,\"radarMetricMinValue\":0},\"avg_market_share\":{\"radarMetricMaxValue\":50,\"radarMetricMinValue\":0}},\"show_legend\":true,\"legendType\":\"scroll\",\"legendOrientation\":\"top\",\"legendMargin\":null,\"legendSort\":null,\"adhoc_filters\":[],\"timeseries_limit_metric\":\"avg_market_share\"}",
  "description": "Compare top 5 products across quality, price, durability, satisfaction, and market share",
  "owners": [1],
  "dashboards": [5]
}
```

## Response Format

The chart creation endpoint returns a response containing the created chart's details:

```json
{
  "id": 123,
  "slice_name": "Product Performance Comparison",
  "viz_type": "radar",
  "datasource_id": 1,
  "datasource_type": "table",
  "description": "Compare top 5 products across quality, price, durability, satisfaction, and market share",
  "cache_timeout": null,
  "owners": [1],
  "dashboards": [5]
}
```

## Notes

- **Groupby and Metrics**: The radar chart requires both `groupby` and `metrics` to be specified. Each unique value in `groupby` creates a separate polygon/series, and each metric becomes an axis on the radar
- **Number of Axes**: Each metric in the `metrics` array creates a separate axis starting from the center. For best readability, use 3-8 metrics (axes). Too many axes can make the chart cluttered
- **Number of Series**: Each unique combination of values in the `groupby` columns creates a separate series (polygon). Use `row_limit` and `timeseries_limit_metric` to control the number of series when dealing with high-cardinality groupby columns
- **Metric Scales**: By default, each axis automatically scales based on the data. Use `column_config` to set custom min/max values for specific metrics, which is useful when:
  - You want consistent scales across different chart instances
  - You know the theoretical min/max of a metric (e.g., percentages from 0-100)
  - You want to normalize different metrics to comparable scales
- **Circle vs Polygon**: The `is_circle` option changes the radar background from a polygon to concentric circles. Circles work well when metrics have similar scales, while polygons are better when axes represent very different types of measurements
- **Label Options**:
  - Use `label_type: "value"` to show just the numeric value
  - Use `label_type: "key_value"` to show both the category name and value
  - Adjust `label_position` to avoid overlapping labels
- **Performance**: For large datasets, adjust `row_limit` to limit the number of series. Too many overlapping polygons can make the chart difficult to read
- **Comparison Strategy**: Radar charts are most effective when:
  - Comparing 2-6 entities (more makes it hard to distinguish)
  - All metrics are normalized to similar scales
  - Higher values consistently mean "better" (or consistently mean "worse") across all metrics
- **Limitations**: Be cautious when interpreting radar charts:
  - The order of axes affects the shape of the polygon
  - The area of the polygon can be misleading if metrics have different scales
  - They work best when comparing relative patterns rather than absolute values
