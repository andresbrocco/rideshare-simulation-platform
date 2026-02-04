# Histogram (`histogram_v2`)

## Description
The Histogram chart displays the distribution of a dataset by representing the frequency or count of values within different ranges or bins. It helps visualize patterns, clusters, and outliers in the data and provides insights into its shape, central tendency, and spread. This ECharts-powered visualization organizes continuous numerical data into discrete bins, making it easier to understand the underlying probability distribution and identify concentration of values.

## When to Use
Use the Histogram when you need to understand the distribution of continuous numerical data, identify the frequency of values within specific ranges, or spot patterns such as normal distributions, skewness, or outliers. This visualization is particularly valuable for statistical analysis, quality control, and exploratory data analysis where understanding the shape and spread of data is essential.

## Example Use Cases
- Analyzing customer age distribution to identify target demographics
- Examining response times to identify performance bottlenecks and outliers
- Reviewing test score distributions to understand class performance
- Monitoring manufacturing measurements to ensure quality control standards
- Evaluating financial data such as transaction amounts or account balances to detect anomalies
- Studying website load times to optimize user experience

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `histogram_v2` |
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
The `params` field should contain a JSON-encoded string with the following properties:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| column | string | Yes | - | Numeric column used to calculate the histogram. Must be a single numeric column from the datasource. This field is required. |
| groupby | array | No | [] | Dimensions to group by. Array of column names to create multiple histogram series for comparison. |
| adhoc_filters | array | No | [] | Array of adhoc filter objects to filter the data before creating the histogram. |
| row_limit | integer | No | 10000 | Maximum number of rows to retrieve from the datasource. |
| bins | integer | No | 5 | The number of bins for the histogram. Determines how many ranges the data is divided into. Accepts values from 5 to 20, or custom integer values. |
| normalize | boolean | No | false | Transforms the histogram values into proportions or probabilities by dividing each bin's count by the total count of data points. When enabled, resulting values sum to 1, enabling relative comparison of the data's distribution. |
| cumulative | boolean | No | false | When enabled, histogram bars represent the running total of frequencies up to each bin. This helps understand how likely it is to encounter values below a certain point. The cumulative option displays data accumulation without changing the original data. |
| color_scheme | string | No | 'supersetColors' | Color scheme to apply to the chart (e.g., 'supersetColors', 'bnbColors', 'd3Category10'). |
| show_value | boolean | No | false | Show series values on the chart. When enabled, displays the count or normalized value on each histogram bar. |
| show_legend | boolean | No | true | Whether to display a legend for the chart. Useful when grouping by dimensions to identify different series. |
| x_axis_title | string | No | '' | Title text for the X-axis. Describes the bins or ranges being displayed. |
| x_axis_format | string | No | 'SMART_NUMBER' | D3 format string for X-axis values (e.g., '.2f', ',d', '.1%', 'SMART_NUMBER'). Controls how bin range labels are formatted. |
| y_axis_title | string | No | '' | Title text for the Y-axis. Typically describes frequency, count, or proportion depending on normalization. |
| y_axis_format | string | No | 'SMART_NUMBER' | D3 format string for Y-axis values (e.g., '.2f', ',d', '.1%', 'SMART_NUMBER'). Controls how frequency values are displayed. |

### Example Request
```json
{
  "slice_name": "Customer Age Distribution",
  "viz_type": "histogram_v2",
  "datasource_id": 123,
  "datasource_type": "table",
  "params": "{\"column\": \"customer_age\", \"groupby\": [], \"bins\": 10, \"normalize\": false, \"cumulative\": false, \"color_scheme\": \"supersetColors\", \"show_value\": true, \"show_legend\": false, \"x_axis_title\": \"Age Range\", \"x_axis_format\": \"SMART_NUMBER\", \"y_axis_title\": \"Number of Customers\", \"y_axis_format\": \",d\", \"adhoc_filters\": [{\"clause\": \"WHERE\", \"comparator\": [\"active\"], \"expressionType\": \"SIMPLE\", \"operator\": \"IN\", \"subject\": \"status\"}], \"row_limit\": 10000}",
  "description": "Distribution of customer ages showing concentration in different age groups",
  "owners": [1]
}
```

### Example Request with Normalization and Cumulative
```json
{
  "slice_name": "Response Time Distribution (Normalized)",
  "viz_type": "histogram_v2",
  "datasource_id": 456,
  "datasource_type": "table",
  "params": "{\"column\": \"response_time_ms\", \"groupby\": [\"server_region\"], \"bins\": 15, \"normalize\": true, \"cumulative\": false, \"color_scheme\": \"d3Category10\", \"show_value\": false, \"show_legend\": true, \"x_axis_title\": \"Response Time (ms)\", \"x_axis_format\": \",.0f\", \"y_axis_title\": \"Probability\", \"y_axis_format\": \".2%\", \"adhoc_filters\": [], \"row_limit\": 50000}",
  "description": "Normalized distribution of API response times by server region",
  "owners": [1, 2],
  "dashboards": [10]
}
```

### Example Request with Cumulative Distribution
```json
{
  "slice_name": "Test Score Cumulative Distribution",
  "viz_type": "histogram_v2",
  "datasource_id": 789,
  "datasource_type": "table",
  "params": "{\"column\": \"test_score\", \"groupby\": [], \"bins\": 20, \"normalize\": false, \"cumulative\": true, \"color_scheme\": \"bnbColors\", \"show_value\": false, \"show_legend\": false, \"x_axis_title\": \"Test Score\", \"x_axis_format\": \"SMART_NUMBER\", \"y_axis_title\": \"Cumulative Count\", \"y_axis_format\": \"SMART_NUMBER\", \"adhoc_filters\": [{\"clause\": \"WHERE\", \"comparator\": \"2024\", \"expressionType\": \"SIMPLE\", \"operator\": \"TEMPORAL_RANGE\", \"subject\": \"test_date\"}], \"row_limit\": 10000}",
  "description": "Cumulative distribution showing the running total of test scores",
  "owners": [3]
}
```

## Notes
- The `column` field is required and must reference a single numeric column. The control panel restricts selection to numeric data types only.
- The `bins` parameter accepts integer values. While the default UI offers choices from 5 to 20 in increments of 5, you can specify any valid integer value in the API request.
- When `normalize` is enabled, the Y-axis values represent proportions (0 to 1) or percentages, making it useful for comparing distributions across different sample sizes.
- The `cumulative` option is particularly useful for understanding percentiles and probability distributions. It shows the proportion of data points that fall below each bin's upper bound.
- Both `normalize` and `cumulative` can be enabled simultaneously to create a cumulative probability distribution.
- When using `groupby` to compare multiple distributions, each group will be displayed as a separate series with different colors from the selected color scheme.
- The histogram automatically calculates bin ranges based on the min/max values in the data and the specified number of bins.
- Adhoc filters can be used to focus the histogram on specific subsets of data without modifying the underlying dataset.
- X-axis and Y-axis format strings follow D3 formatting conventions. Use `SMART_NUMBER` for automatic intelligent formatting.
- The histogram requires at least one data point in the selected column. Empty result sets will cause an error.
- This chart type is built with Apache ECharts and is part of the ECharts plugin suite.
