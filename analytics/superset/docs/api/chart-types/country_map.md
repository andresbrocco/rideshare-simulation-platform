# Country Map (`country_map`)

## Description
The Country Map visualization displays a choropleth map showing how a single metric varies across a country's principal subdivisions such as states, provinces, departments, or regions. Each geographic boundary is color-coded based on the metric value, and hovering over a region displays detailed information about that subdivision's value.

## When to Use
Use this chart type when you need to visualize geographic distribution of a metric within a specific country's administrative divisions. It is particularly effective for regional comparisons, identifying geographic patterns, and highlighting areas of high or low performance within a country's subdivisions.

## Example Use Cases
- Sales performance by state or province
- Population density across regions
- Disease prevalence by administrative division
- Customer distribution by geographic subdivision
- Regional revenue comparison across a country
- Political polling results by state or province

## Request Format

### Common Fields
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| slice_name | string | Yes | Chart name (max 250 chars) |
| viz_type | string | Yes | Must be `country_map` |
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
| select_country | string | Yes | null | Country identifier specifying which country's map to plot. See supported countries list below. |
| entity | string/object | Yes | null | Column containing ISO 3166-2 codes of region/province/department. Can be a column name (string) or an adhoc column definition (object). |
| metric | string/object | Yes | null | Metric to display and use for the bottom title. Can be a saved metric name (string) or an adhoc metric definition (object). |
| adhoc_filters | array | No | [] | List of adhoc filter objects to apply to the data |
| number_format | string | No | 'SMART_NUMBER' | D3 format string for formatting the metric values (e.g., '.3s', '.2f', ',.0f') |
| linear_color_scheme | string | No | (default sequential scheme) | Color scheme to use for the choropleth. Must be a valid sequential color scheme ID. |
| row_limit | integer | No | 10000 | Maximum number of rows to retrieve from the datasource |

#### Adhoc Metric Format
When specifying an adhoc metric, use the following structure:
```json
{
  "expressionType": "SIMPLE" | "SQL",
  "aggregate": "AVG" | "COUNT" | "COUNT_DISTINCT" | "MAX" | "MIN" | "SUM",
  "column": {
    "column_name": "column_name",
    "type": "BIGINT" | "VARCHAR" | etc.
  },
  "sqlExpression": "SQL expression (for SQL type only)",
  "label": "Display label",
  "hasCustomLabel": true | false
}
```

#### Adhoc Filter Format
When specifying adhoc filters, use the following structure:
```json
{
  "col": "column_name or adhoc column object",
  "op": "IN" | "NOT IN" | "==" | "!=" | ">" | "<" | ">=" | "<=" | "LIKE" | etc.,
  "val": "value or array of values"
}
```

#### Supported Countries
The `select_country` field accepts the following country identifiers:
- `afghanistan`, `aland`, `albania`, `algeria`, `american_samoa`, `andorra`, `angola`, `anguilla`, `antarctica`, `antigua_and_barbuda`, `argentina`, `armenia`, `australia`, `austria`, `azerbaijan`, `bahrain`, `bangladesh`, `barbados`, `belarus`, `belgium`, `belize`, `benin`, `bermuda`, `bhutan`, `bolivia`, `bosnia_and_herzegovina`, `botswana`, `brazil`, `brunei`, `bulgaria`, `burkina_faso`, `burundi`, `cambodia`, `cameroon`, `canada`, `cape_verde`, `central_african_republic`, `chad`, `chile`, `china`, `colombia`, `comoros`, `cook_islands`, `costa_rica`, `croatia`, `cuba`, `cyprus`, `czech_republic`, `democratic_republic_of_the_congo`, `denmark`, `djibouti`, `dominica`, `dominican_republic`, `ecuador`, `egypt`, `el_salvador`, `equatorial_guinea`, `eritrea`, `estonia`, `ethiopia`, `fiji`, `finland`, `france`, `france_overseas`, `france_regions`, `french_polynesia`, `gabon`, `gambia`, `germany`, `ghana`, `greece`, `greenland`, `grenada`, `guatemala`, `guinea`, `guyana`, `haiti`, `honduras`, `hungary`, `iceland`, `india`, `indonesia`, `iran`, `israel`, `italy`, `italy_regions`, `ivory_coast`, `japan`, `jordan`, `kazakhstan`, `kenya`, `korea`, `kuwait`, `kyrgyzstan`, `laos`, `latvia`, `lebanon`, `lesotho`, `liberia`, `libya`, `liechtenstein`, `lithuania`, `luxembourg`, `macedonia`, `madagascar`, `malawi`, `malaysia`, `maldives`, `mali`, `malta`, `marshall_islands`, `mauritania`, `mauritius`, `mexico`, `moldova`, `mongolia`, `montenegro`, `montserrat`, `morocco`, `mozambique`, `myanmar`, `namibia`, `nauru`, `nepal`, `netherlands`, `new_caledonia`, `new_zealand`, `nicaragua`, `niger`, `nigeria`, `northern_mariana_islands`, `norway`, `oman`, `pakistan`, `palau`, `panama`, `papua_new_guinea`, `paraguay`, `peru`, `philippines`, `philippines_regions`, `poland`, `portugal`, `qatar`, `republic_of_serbia`, `romania`, `russia`, `rwanda`, `saint_lucia`, `saint_pierre_and_miquelon`, `saint_vincent_and_the_grenadines`, `samoa`, `san_marino`, `sao_tome_and_principe`, `saudi_arabia`, `senegal`, `seychelles`, `sierra_leone`, `singapore`, `slovakia`, `slovenia`, `solomon_islands`, `somalia`, `south_africa`, `spain`, `sri_lanka`, `sudan`, `suriname`, `sweden`, `switzerland`, `syria`, `taiwan`, `tajikistan`, `tanzania`, `thailand`, `the_bahamas`, `timorleste`, `togo`, `tonga`, `trinidad_and_tobago`, `tunisia`, `turkey`, `turkey_regions`, `turkmenistan`, `turks_and_caicos_islands`, `uganda`, `uk`, `ukraine`, `united_arab_emirates`, `united_states_minor_outlying_islands`, `united_states_virgin_islands`, `uruguay`, `usa`, `uzbekistan`, `vanuatu`, `venezuela`, `vietnam`, `wallis_and_futuna`, `yemen`, `zambia`, `zimbabwe`

Note: Some countries have regional variants (e.g., `france_regions`, `italy_regions`, `philippines_regions`, `turkey_regions`) and special versions (e.g., `france_overseas`).

### Example Request
```json
{
  "slice_name": "US Sales by State",
  "viz_type": "country_map",
  "datasource_id": 123,
  "datasource_type": "table",
  "params": "{\"select_country\":\"usa\",\"entity\":\"state_code\",\"metric\":{\"expressionType\":\"SIMPLE\",\"aggregate\":\"SUM\",\"column\":{\"column_name\":\"sales_amount\",\"type\":\"DECIMAL\"},\"label\":\"Total Sales\",\"hasCustomLabel\":true},\"adhoc_filters\":[{\"col\":\"year\",\"op\":\"==\",\"val\":2024}],\"number_format\":\"$,.2f\",\"linear_color_scheme\":\"blue_white_yellow\",\"row_limit\":10000}",
  "description": "Total sales amount by US state for 2024",
  "cache_timeout": 3600,
  "dashboards": [456],
  "owners": [789]
}
```

### Example params Object (before JSON stringification)
```json
{
  "select_country": "usa",
  "entity": "state_code",
  "metric": {
    "expressionType": "SIMPLE",
    "aggregate": "SUM",
    "column": {
      "column_name": "sales_amount",
      "type": "DECIMAL"
    },
    "label": "Total Sales",
    "hasCustomLabel": true
  },
  "adhoc_filters": [
    {
      "col": "year",
      "op": "==",
      "val": 2024
    }
  ],
  "number_format": "$,.2f",
  "linear_color_scheme": "blue_white_yellow",
  "row_limit": 10000
}
```

## Notes
- The `entity` column must contain valid ISO 3166-2 subdivision codes that match the selected country (e.g., "US-CA" for California when using the USA map)
- The chart uses a choropleth visualization where regions are shaded based on the metric value
- Hovering over a region displays the region name and metric value
- The color scheme is sequential, meaning it uses a continuous gradient from low to high values
- This chart type uses the legacy API (`useLegacyApi: true`), which may have different query patterns than newer chart types
