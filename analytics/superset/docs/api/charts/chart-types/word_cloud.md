# Word Cloud (`word_cloud`)

## Description
The Word Cloud chart visualizes the frequency of words or categorical values where the size of each word corresponds to its frequency or associated metric value. Words that appear more frequently are displayed in larger font sizes, creating an intuitive visual representation of which items are most prevalent in the dataset. The chart uses the d3-cloud library to intelligently arrange words within the available space, with configurable rotation and color schemes to enhance visual appeal and readability.

## When to Use
Use this chart when you want to quickly identify the most common or significant items in a categorical dataset. It is particularly effective for text analysis, tag clouds, category frequency visualization, or any scenario where you want to highlight the relative importance of different items through visual size. The word cloud excels at making patterns in categorical data immediately apparent to viewers without requiring detailed analysis.

## Example Use Cases
- Displaying the most frequently used product tags or keywords in customer reviews
- Visualizing the distribution of support ticket categories to identify common issues
- Showing the popularity of different search terms on a website
- Highlighting the most common skills or technologies mentioned in job postings
- Analyzing the frequency of topics or hashtags in social media content
- Displaying customer feedback themes with size proportional to mention frequency

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `word_cloud` |
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
The `params` field must be a JSON-encoded string containing an object with the following fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| series | string/object | Yes | - | The categorical column containing the words or labels to display |
| metric | string/object | Yes | - | The metric that determines the size of each word (e.g., count, sum) |
| adhoc_filters | array | No | [] | Filters to apply to the data |
| row_limit | integer | No | 100 | Maximum number of words to display |
| sort_by_metric | boolean | No | false | Whether to sort results by the selected metric in descending order |
| size_from | integer | No | 10 | Minimum font size in pixels for the smallest word |
| size_to | integer | No | 70 | Maximum font size in pixels for the largest word |
| rotation | string | No | 'square' | Word rotation pattern: 'flat' (no rotation), 'square' (0° or 90°), or 'random' (random angles) |
| color_scheme | string | No | 'supersetColors' | Color scheme to use for the words |

### Example Request
```json
{
  "slice_name": "Product Category Popularity",
  "viz_type": "word_cloud",
  "datasource_id": 42,
  "datasource_type": "table",
  "params": "{\"series\": \"category_name\", \"metric\": {\"aggregate\": \"COUNT\", \"column\": {\"column_name\": \"product_id\"}, \"expressionType\": \"SIMPLE\", \"label\": \"Product Count\"}, \"adhoc_filters\": [], \"row_limit\": 100, \"sort_by_metric\": true, \"size_from\": 10, \"size_to\": 70, \"rotation\": \"square\", \"color_scheme\": \"supersetColors\"}",
  "description": "Displays product categories sized by the number of products in each category",
  "owners": [1],
  "dashboards": [5]
}
```

## Parameter Details

### Series Field
The `series` field defines which column contains the words or categorical values to display. This can be specified as:
- A string containing the column name: `"category_name"`
- An object for more complex column references

This field is required and must not be empty. Each unique value in this column becomes a word in the cloud.

### Metric Field
The `metric` field determines the size of each word. It can be:
- A string referencing a saved metric: `"count"`
- An ad-hoc metric object with aggregation:
  ```json
  {
    "aggregate": "COUNT",
    "column": {"column_name": "product_id"},
    "expressionType": "SIMPLE",
    "label": "Product Count"
  }
  ```
- An ad-hoc SQL metric for custom calculations:
  ```json
  {
    "expressionType": "SQL",
    "sqlExpression": "SUM(price * quantity)",
    "label": "Total Revenue"
  }
  ```

### Row Limit
The `row_limit` parameter controls how many words appear in the cloud:
- Default: 100
- Higher values show more words but may make the visualization cluttered
- Lower values focus on the most significant items
- The chart intelligently scales words to fit the available space

### Font Size Range
The `size_from` and `size_to` parameters control the font size range:
- `size_from`: Minimum font size in pixels (default: 10)
- `size_to`: Maximum font size in pixels (default: 70)
- The chart scales word sizes linearly between these values based on metric values
- Larger ranges create more dramatic size differences
- Smaller ranges create more uniform word sizes

### Rotation Options
The `rotation` field controls how words are oriented:

| Value | Description | Visual Effect |
|-------|-------------|---------------|
| `flat` | All words horizontal (0°) | Most readable, best for dense text |
| `square` | Random 0° or 90° rotation | Balanced look, fits more words |
| `random` | Random angles (-60°, -30°, 0°, 30°, 60°, 90°) | Dynamic appearance, artistic effect |

- `flat` is recommended for readability when word length varies significantly
- `square` is the default and provides good space utilization
- `random` creates visual interest but may reduce readability

### Color Scheme
The `color_scheme` field specifies which color palette to use for the words. Common options include:
- `supersetColors` - Default Superset color palette
- `bnbColors` - Airbnb color scheme
- `lyftColors` - Lyft color scheme
- `googleCategory10c` - Google 10-color categorical scheme
- `d3Category10` - D3 10-color categorical scheme
- `preset` - Preset.io color scheme

Colors are assigned to words based on the series values. The same word will maintain consistent color across chart updates.

### Adhoc Filters
The `adhoc_filters` field allows you to filter the data before visualization:
```json
"adhoc_filters": [
  {
    "col": "status",
    "op": "IN",
    "val": ["active", "pending"]
  },
  {
    "col": "created_date",
    "op": "TEMPORAL_RANGE",
    "val": "Last month"
  }
]
```

Filter operators include:
- `IN` / `NOT IN` - Match list of values
- `==` / `!=` - Exact match / not match
- `>` / `>=` / `<` / `<=` - Numeric comparisons
- `LIKE` / `ILIKE` - Pattern matching (case-sensitive / case-insensitive)
- `TEMPORAL_RANGE` - Time-based filtering

### Sort by Metric
When `sort_by_metric` is enabled:
- Results are sorted by the metric value in descending order
- Combined with `row_limit`, this ensures only the top N items are shown
- Disabled by default to preserve the natural data ordering

## Advanced Configuration

### Encoding Configuration
While not directly exposed in the API, the word cloud supports advanced encoding through the `encoding` parameter in the params object for programmatic customization:

```json
"encoding": {
  "color": {
    "field": "category",
    "scale": {"scheme": "supersetColors"}
  },
  "fontSize": {
    "field": "count",
    "scale": {"range": [10, 70], "zero": true}
  },
  "text": {
    "field": "word"
  }
}
```

This allows fine-grained control over how data fields map to visual properties, though most use cases are covered by the standard parameters.

## Performance Considerations

### Optimization Tips
1. Use appropriate `row_limit` values:
   - 50-100 words: Optimal for most dashboards
   - 100-200 words: Good for detailed analysis
   - 200+ words: May impact performance and readability

2. Font size scaling:
   - Larger size ranges (e.g., 10-100) work better with fewer words
   - Moderate ranges (e.g., 15-50) work well for dense clouds

3. The chart automatically scales to fit words:
   - If words do not fit initially, the chart increases canvas size up to 3x
   - This ensures top results (top 10% by metric) always appear
   - Very large word counts may take longer to render

### Caching
Consider setting `cache_timeout` for word clouds that:
- Query large datasets
- Are frequently viewed
- Have relatively stable underlying data
- Typical values: 300-3600 seconds (5 minutes to 1 hour)

## Common Issues and Solutions

### Words Not Appearing
If some words are missing from the cloud:
- Increase `row_limit` to include more results
- Verify the metric produces non-zero values for those words
- Check that filters are not excluding the data

### Words Too Small or Too Large
If word sizes are not well-distributed:
- Adjust `size_from` and `size_to` to a narrower or wider range
- Check for outliers in your metric values that may skew scaling
- Consider using a different aggregation function for the metric

### Poor Readability
If words are difficult to read:
- Use `rotation: "flat"` for maximum readability
- Reduce `row_limit` to show fewer, larger words
- Increase the minimum font size (`size_from`)

### Color Issues
If colors appear inconsistent or unexpected:
- Try a different `color_scheme` with better contrast
- Ensure color scheme is appropriate for your dashboard theme
- Note that colors persist based on the series value, not position
