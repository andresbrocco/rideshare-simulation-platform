# Paired T-Test (`paired_ttest`)

## Description
A table visualization that displays paired t-test results, which are statistical tests used to understand significant differences between groups. The chart compares metrics across different groups and calculates p-values, lift values, and statistical significance to help identify meaningful patterns in the data.

## When to Use
Use paired t-test tables when you need to statistically compare metric values between different groups to determine if observed differences are statistically significant or likely due to random variation. This chart type is particularly effective for A/B testing, experiment analysis, and comparing performance across segments.

## Example Use Cases
- A/B testing analysis comparing conversion rates between control and variant groups
- Evaluating the impact of product changes or features across different user segments
- Comparing sales performance between different time periods or regions
- Analyzing marketing campaign effectiveness across different customer cohorts
- Testing the statistical significance of changes in key performance indicators (KPIs)

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `paired_ttest` |
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
| metrics | array | Yes | - | One or more metrics to compare between groups. Each metric can be an aggregation function on a column or custom SQL expression. |
| groupby | array | Yes | - | Categories that define the groups to compare. Required to have at least one dimension. Dimensions contain qualitative values for categorizing data. |
| adhoc_filters | array | No | [] | Filters to apply to the chart query. Can be simple column filters or custom SQL expressions. |
| limit | integer | No | null | Limits the number of series displayed. Applied via subquery to limit fetched data. Useful for high cardinality groupings. |
| timeseries_limit_metric | object/string | No | null | Metric used to determine which series to keep when series limit is applied. Defaults to first metric if undefined. |
| order_desc | boolean | No | true | If enabled, sorts results descending; otherwise sorts ascending. Only visible when timeseries_limit_metric is set. |
| contribution | boolean | No | false | When enabled, computes the contribution of each value to the total. |
| row_limit | integer | No | 10000 | Limits the number of rows computed in the source query. Options: 10, 50, 100, 250, 500, 1000, 5000, 10000, 50000. |
| significance_level | number | No | 0.05 | Threshold alpha level for determining statistical significance. Common values are 0.05 (95% confidence) or 0.01 (99% confidence). |
| pvalue_precision | integer | No | 6 | Number of decimal places with which to display p-values in the table. |
| liftvalue_precision | integer | No | 4 | Number of decimal places with which to display lift percent values in the table. |

### Example Request
```json
{
  "slice_name": "A/B Test: New Checkout Flow vs Control",
  "viz_type": "paired_ttest",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"metrics\": [{\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"conversion_rate\", \"type\": \"DOUBLE\"}, \"aggregate\": \"AVG\", \"label\": \"Avg Conversion Rate\"}, {\"expressionType\": \"SIMPLE\", \"column\": {\"column_name\": \"revenue\", \"type\": \"DOUBLE\"}, \"aggregate\": \"SUM\", \"label\": \"Total Revenue\"}], \"groupby\": [\"experiment_group\"], \"adhoc_filters\": [{\"clause\": \"WHERE\", \"expressionType\": \"SIMPLE\", \"subject\": \"experiment_active\", \"operator\": \"==\", \"comparator\": true}], \"limit\": null, \"timeseries_limit_metric\": null, \"order_desc\": true, \"contribution\": false, \"row_limit\": 10000, \"significance_level\": 0.05, \"pvalue_precision\": 6, \"liftvalue_precision\": 4}",
  "description": "Statistical comparison of conversion rates and revenue between new checkout flow and control group",
  "owners": [1]
}
```

## Response Format

The API returns a chart object with the following structure:

```json
{
  "id": 123,
  "slice_name": "A/B Test: New Checkout Flow vs Control",
  "viz_type": "paired_ttest",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{...}",
  "description": "Statistical comparison of conversion rates and revenue between new checkout flow and control group",
  "cache_timeout": null,
  "owners": [1],
  "created_on": "2026-02-03T12:00:00",
  "changed_on": "2026-02-03T12:00:00"
}
```

## Notes

- **Statistical Testing**: The paired t-test compares means between groups and calculates:
  - **P-value**: Probability that the observed difference occurred by chance. Lower values indicate stronger evidence of a real difference.
  - **Lift Value**: Percentage change or difference between groups, showing the magnitude of the effect.
  - **Significance**: Based on the significance_level (alpha), the test determines if differences are statistically significant.

- **Significance Level**: The `significance_level` parameter (default 0.05) represents the threshold for statistical significance:
  - 0.05 means 95% confidence level (p-values < 0.05 are considered significant)
  - 0.01 means 99% confidence level (p-values < 0.01 are considered significant)
  - Lower alpha values require stronger evidence to reject the null hypothesis

- **Group Requirements**: At least one groupby dimension is required to define the groups being compared. The chart compares all pairs of groups for each metric.

- **Precision Settings**:
  - `pvalue_precision` controls decimal places for p-values (max 32)
  - `liftvalue_precision` controls decimal places for lift percentages (max 32)
  - Higher precision may be useful for very small p-values or precise lift calculations

- **Display**: Results are shown in a sortable table format with one table per metric, displaying comparisons between all group pairs with their corresponding statistical measures.

- **Legacy Chart**: This is a legacy chart type using the legacy API format. For new implementations, consider modern statistical visualization alternatives or consult with data science teams about appropriate statistical tests for your use case.
