# AG Grid Table (`ag-grid-table`)

## Description

The AG Grid Table chart displays data in a modern, high-performance spreadsheet format powered by AG Grid. This visualization provides an advanced tabular view with enterprise-grade features including sorting, pagination, search functionality, conditional formatting, column customization, and visual enhancements like cell bars. The AG Grid Table (also known as Table V2) supports both raw data records and aggregated metrics, making it suitable for detailed data exploration, reporting, and interactive data analysis.

## When to Use

Use this chart when you need a modern, feature-rich table with advanced capabilities beyond the standard table chart. The AG Grid Table excels at handling large datasets with smooth scrolling, flexible column management, and powerful filtering options. It's ideal when precise values matter more than visual patterns, or when you need to present multiple metrics and dimensions together with enhanced user interactions. The chart supports both aggregate queries (with GROUP BY) and raw data queries, offering flexibility for different analytical needs.

## Example Use Cases

- Building high-performance dashboards with large datasets requiring smooth scrolling and pagination
- Creating executive summary reports with aggregated metrics grouped by region or time period
- Displaying detailed sales records with customer information, order amounts, and dates with advanced filtering
- Building searchable product catalogs with multiple attributes and custom column configurations
- Presenting comparison tables with time-over-time metrics showing absolute and percentage changes
- Creating interactive data browsers with server-side pagination for millions of records
- Displaying financial statements with conditional formatting and cell bars to highlight trends
- Building data exploration tools with column reordering and customizable views

---

# Big Number (`big_number`)

## Description

The Big Number with Trendline chart showcases a single prominent metric value accompanied by a simple line chart. This visualization is designed to call attention to an important KPI (Key Performance Indicator) along with its change over time or other dimensions. The large number display makes the current metric value immediately visible, while the trendline provides visual context about the metric's historical behavior.

## When to Use

Use this chart when you need to highlight a critical metric that stakeholders need to monitor at a glance. It's particularly effective in dashboards and executive reports where you want to combine the impact of a single numeric value with the context of its trend over time. This visualization works best when the metric's historical pattern is as important as its current value.

## Example Use Cases

- Displaying monthly recurring revenue (MRR) with a trendline showing growth over the past 12 months
- Tracking daily active users (DAU) with a weekly trend comparison
- Monitoring server response time with performance trends to identify degradation
- Showing total sales for the current quarter alongside historical sales patterns
- Displaying current inventory levels with a trendline to predict stockouts

---

# Big Number Total (`big_number_total`)

## Description

The Big Number Total chart showcases a single metric in a large, prominent display format. It's designed to call immediate attention to a key performance indicator (KPI) or critical metric, displaying the value front-and-center with optional subtitle text below for additional context.

## When to Use

Use Big Number Total when you want to focus your audience's attention on one specific metric or KPI. This chart type is ideal for executive dashboards, status displays, or any scenario where a single number tells the most important part of the story.

## Example Use Cases

- Display total revenue for the current quarter on an executive dashboard
- Show the current number of active users or customers
- Monitor real-time inventory levels or stock counts
- Track total sales, orders, or conversions for a given time period
- Display key operational metrics like uptime percentage or error counts

---

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

---

# Bubble Chart (Legacy) (`bubble`)

## Description

The Bubble Chart visualizes data across three quantitative dimensions simultaneously using the X-axis position, Y-axis position, and bubble size. Bubbles can be grouped by a categorical dimension (series) with each series represented by a distinct color, enabling comparison of multiple groups across three numeric metrics in a single visualization. **Note**: this chart type is marked as **deprecated** and uses the legacy NVD3 library.

## When to Use

Use this chart type when you need to analyze relationships between three continuous variables and optionally compare different categories. It is particularly effective for identifying correlations, patterns, and outliers across multiple dimensions, such as comparing market segments by revenue, growth rate, and market size.

## Example Use Cases

- Analyzing product performance by sales volume (X), profit margin (Y), and market share (bubble size) across different product categories (series)
- Comparing countries by GDP per capita (X), life expectancy (Y), and population (bubble size) across continents
- Evaluating marketing campaigns by cost (X), conversions (Y), and reach (bubble size) across different channels
- Visualizing employee performance by experience (X), productivity (Y), and project count (bubble size) across departments
- Studying competitor analysis by price point (X), customer satisfaction (Y), and market share (bubble size)

---

# Bubble Chart (`bubble_v2`)

## Description

The Bubble Chart visualizes data across three dimensions in a single chart: X-axis position, Y-axis position, and bubble size. Each bubble represents a data point, with its position determined by X and Y values and its size determined by a metric. Bubbles can be grouped and colored by series to show relationships across an additional dimension, making it ideal for multi-dimensional correlation analysis.

## When to Use

Use a Bubble Chart when you need to display relationships between three or more quantitative variables simultaneously. It's particularly effective for identifying patterns, clusters, and outliers across multiple dimensions. The chart works best when you have a moderate number of data points that won't overcrowd the visualization space.

## Example Use Cases

- Analyzing product performance by plotting price (X-axis) vs. sales volume (Y-axis) with bubble size representing profit margin, grouped by product category
- Comparing countries by GDP per capita (X-axis) vs. life expectancy (Y-axis) with population as bubble size, colored by continent
- Evaluating marketing campaigns by cost (X-axis) vs. reach (Y-axis) with conversion rate as bubble size, grouped by channel
- Visualizing website metrics by plotting page load time (X-axis) vs. bounce rate (Y-axis) with traffic volume as bubble size, colored by device type
- Examining real estate properties by square footage (X-axis) vs. price (Y-axis) with number of bedrooms as bubble size, grouped by neighborhood

---

# Bullet Chart (`bullet`)

## Description

A Bullet Chart is a variation of a bar chart designed to showcase the progress of a single metric against a given target. The chart features a horizontal bar representing the actual metric value, with background shading for contextual ranges and markers (triangles or lines) to indicate targets or reference points. The higher the fill of the bar, the closer the metric is to achieving its target.

## When to Use

Use a Bullet Chart when you need to display performance metrics against goals or benchmarks in a compact, easy-to-read format. This chart type is ideal for KPI dashboards where space efficiency is important and you want to show not just current performance, but also contextual ranges (like "poor", "satisfactory", "good") and specific target values.

## Example Use Cases

- Tracking sales revenue against quarterly targets with performance ranges
- Monitoring server response times against SLA thresholds
- Displaying customer satisfaction scores with industry benchmark markers
- Showing project completion percentage against planned milestones
- Comparing actual expenses against budget allocations with warning zones

---

# Calendar Heatmap (`cal_heatmap`)

## Description

The Calendar Heatmap visualizes how a metric has changed over time using a color scale and a calendar view. It displays data in a grid format where each cell represents a time period (such as a day, hour, or week), and the cell's color intensity indicates the magnitude of the metric value for that period. Gray values indicate missing data, and a linear color scheme encodes the magnitude of each period's value.

## When to Use

Use a Calendar Heatmap when you need to identify patterns, trends, or anomalies in time-series data over extended periods. This visualization is particularly effective for showing temporal patterns like seasonality, weekly cycles, or recurring events. It works best with single-metric data aggregated over regular time intervals where you want to compare intensity across days, weeks, months, or years at a glance.

## Example Use Cases

- **Website Traffic Analysis**: Visualize daily page views or user sessions to identify peak traffic days and seasonal patterns
- **Sales Performance Tracking**: Display daily or weekly sales revenue to spot trends, identify slow periods, and plan inventory
- **System Health Monitoring**: Track daily error rates, server uptime percentages, or API response times to detect anomalies
- **Employee Productivity**: Monitor task completion rates, support ticket resolutions, or time logged per day across teams
- **Social Media Engagement**: Analyze daily post engagement metrics like likes, shares, or comments to optimize posting schedules

---

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

---

# Chord Diagram (`chord`)

## Description

A Chord Diagram is a circular visualization that shows the flow or relationships between categories using arcs (chords) that connect different segments around a circle. The thickness of each chord represents the magnitude of the relationship, and importantly, the value and corresponding thickness can be different for each direction of the relationship, making it ideal for displaying asymmetric flows.

## When to Use

Use a Chord Diagram when you need to visualize relationships, flows, or connections between different categories where the direction and magnitude matter. This chart is particularly effective when you want to show reciprocal relationships or when the flow from A to B differs from the flow from B to A.

## Example Use Cases

- Visualizing migration patterns between countries or regions (showing both immigration and emigration flows)
- Analyzing trade relationships between different business units or partners
- Displaying communication patterns between teams or departments
- Showing financial flows between different accounts or entities
- Mapping relationships between community channels or social network connections

---

# Compare Chart (`compare`)

## Description

The Compare chart (also known as Time-series Percent Change) visualizes multiple time-series objects in a single chart, allowing you to compare trends and percent changes across different time periods or series. This chart displays data as line graphs with configurable axes, annotations, and advanced analytics capabilities. Note: This chart is deprecated and the Time-series Chart is recommended as a replacement.

## When to Use

Use the Compare chart when you need to visualize and compare multiple time-series metrics or dimensions simultaneously on a single chart with percent change calculations. This visualization is particularly useful for tracking trends over time and comparing historical performance across different periods using advanced analytical features like rolling windows and time shifts.

## Example Use Cases

- Comparing sales revenue growth across different product categories over time
- Analyzing website traffic percent changes between different marketing campaigns
- Tracking year-over-year performance metrics with time shift comparisons
- Monitoring multiple KPIs with rolling average calculations to smooth out fluctuations
- Visualizing seasonal trends with time comparison overlays showing previous periods

---

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

---

# Area Chart (`echarts_area`)

## Description

The Area Chart is a time-series visualization that displays quantitative data over a continuous time interval. It combines line chart elements with filled areas beneath the lines, making it effective for showing cumulative totals and the magnitude of change over time. Multiple series can be stacked on top of each other to show part-to-whole relationships.

## When to Use

Area charts are ideal when you need to emphasize the magnitude of change over time and show trends in data. They work particularly well when displaying cumulative values or when you want to show how multiple data series contribute to a total. The filled area provides a strong visual emphasis on the volume of data, making trends and patterns more apparent than simple line charts.

## Example Use Cases

- Tracking website traffic or user engagement metrics over time, with different areas representing different traffic sources
- Visualizing sales revenue across multiple product categories over fiscal quarters, showing both individual and cumulative performance
- Monitoring resource consumption (CPU, memory, bandwidth) across multiple servers or services over time
- Displaying inventory levels for different product lines throughout the year
- Analyzing population growth across different demographic segments over decades

---

# Timeseries Chart (`echarts_timeseries`)

## Description

The Generic Chart is a versatile time-series visualization that serves as a Swiss army knife for visualizing temporal data. It supports multiple chart types (line, scatter, bar, and step) through the `seriesType` parameter, allowing you to switch between visualization styles without changing the chart type. This chart includes comprehensive customization options for axes, legends, tooltips, and supports advanced analytics features including forecasting, rolling windows, and time comparisons. Built on Apache ECharts, it provides smooth animations and interactive behaviors.

## When to Use

Use the Generic Chart when you need maximum flexibility in visualizing time-series data without committing to a specific visualization style. This chart is ideal when you want to experiment with different visual representations of the same data, or when you need a single chart configuration that can adapt to different presentation needs. It is particularly useful for dashboards where users may want to toggle between different visualization styles, or when building reusable chart templates.

## Example Use Cases

- Creating a flexible dashboard where users can switch between line, bar, and scatter views of the same metrics
- Building chart templates that can adapt to different data visualization needs
- Prototyping time-series visualizations before committing to a specific chart type
- Analyzing data that may benefit from different visualization approaches at different zoom levels
- Displaying metrics that combine multiple series types (though `mixed_timeseries` may be better for this)
- Creating educational dashboards that demonstrate different ways to visualize the same data

---

# Bar Chart (`echarts_timeseries_bar`)

## Description

The Bar Chart is a time-series visualization that displays metrics as vertical or horizontal bars along a temporal axis. Each bar represents a data point at a specific time interval, making it ideal for comparing values across time periods. The chart supports multiple series, stacking, advanced analytics features like forecasting and rolling windows, and rich customization options for axes, legends, and tooltips.

## When to Use

Use the Bar Chart when you need to compare discrete time-based data points, emphasize individual values rather than trends, or display categorical breakdowns over time. Bar charts are particularly effective for showing changes in fixed time intervals and highlighting differences between categories at specific points in time.

## Example Use Cases

- Monthly sales revenue comparison across different product lines
- Daily user signups by registration source over a quarter
- Quarterly budget allocation by department
- Weekly inventory levels by warehouse location
- Hourly website traffic by geographic region

---

# Line Chart (`echarts_timeseries_line`)

## Description

The Line Chart is a time-series visualization that displays information as a series of data points connected by straight line segments. It is used to visualize measurements taken over a given category, making it ideal for showing trends and patterns in data over time. The chart supports multiple series, advanced analytics features including forecasting and rolling windows, and rich customization options for axes, legends, and tooltips.

## When to Use

Use the Line Chart when you need to visualize trends over time, compare multiple metrics or categories, or show continuous data. Line charts excel at revealing patterns, identifying peaks and valleys, and making it easy to see how values change across a temporal dimension. They are particularly effective when you want to emphasize the rate of change rather than the magnitude of values.

## Example Use Cases

- Tracking stock prices or cryptocurrency values over time
- Monitoring website traffic patterns across different channels
- Analyzing temperature or weather trends over seasons
- Comparing sales performance across multiple regions over quarters
- Visualizing user engagement metrics (daily active users, session duration) over weeks or months
- Displaying server response times or application performance metrics over time

---

# Scatter Plot (`echarts_timeseries_scatter`)

## Description

The Scatter Plot is a time-series visualization that displays data points as individual markers without connecting lines. The horizontal axis uses linear units, and points are displayed in order, making it ideal for showing the statistical relationship between two variables. Unlike traditional line charts, scatter plots emphasize individual data points rather than trends, making them excellent for identifying patterns, correlations, and outliers in time-series data.

## When to Use

Use the Scatter Plot when you need to visualize the distribution of individual data points over time, identify correlations between variables, or detect outliers and anomalies. Scatter plots are particularly effective when you want to see the density and spread of data points rather than focusing on continuous trends. They excel at revealing patterns in noisy data where line charts might obscure individual observations.

## Example Use Cases

- Analyzing sensor data or IoT measurements to identify anomalies or outliers over time
- Visualizing stock trading volumes at specific price points throughout the day
- Examining the relationship between temperature and energy consumption across different time periods
- Detecting patterns in server response times or latency measurements over time
- Studying customer purchase behavior by showing transaction amounts over time
- Monitoring quality control metrics where individual measurements matter more than trends

---

# Smooth Line Chart (`echarts_timeseries_smooth`)

## Description

The Smooth Line Chart is a time-series visualization that displays information as a series of data points connected by smooth, curved line segments. Without angles and hard edges, smooth lines sometimes look smarter and more professional compared to regular line charts. It is used to visualize measurements taken over a given category, making it ideal for showing trends and patterns in data over time. The chart supports multiple series, advanced analytics features including forecasting and rolling windows, and rich customization options for axes, legends, and tooltips.

## When to Use

Use the Smooth Line Chart when you need to visualize trends over time with a more polished, professional appearance. The smooth curves are particularly effective for emphasizing continuity and flow in data, making patterns easier to perceive visually. Choose smooth lines over regular lines when you want to de-emphasize individual data points and focus on overall trends, or when the aesthetic quality of the visualization is important for presentations and reports.

## Example Use Cases

- Visualizing temperature trends with smooth transitions between readings
- Displaying revenue growth curves with a professional, polished appearance
- Showing user growth trends for executive presentations
- Tracking smooth variations in metrics like engagement scores or satisfaction ratings
- Creating aesthetically pleasing dashboards for public-facing reports
- Analyzing gradual changes in scientific measurements or sensor data where smooth interpolation is appropriate

---

# Stepped Line Chart (`echarts_timeseries_step`)

## Description

The Stepped Line Chart (also called step chart) is a variation of the line chart where the line forms a series of steps between data points rather than connecting them with straight diagonal lines. Each segment is rendered as a horizontal line at the value level, with vertical lines connecting different value levels. This chart type is particularly useful for showing changes that occur at irregular intervals and for visualizing data where values remain constant between measurement points, such as inventory levels, status changes, or discrete state transitions.

## When to Use

Use the Stepped Line Chart when you need to visualize data that changes in discrete steps rather than continuously. This chart type is ideal for showing values that remain constant between specific points in time and then jump to a new level. It emphasizes the duration for which a value remains constant and clearly shows the exact timing of changes, making it superior to regular line charts for representing step functions, state machines, or any data where intermediate values between measurements don't exist or aren't meaningful.

## Example Use Cases

- Tracking inventory levels over time (stock remains constant until a sale or restock occurs)
- Visualizing pricing changes where prices stay constant until explicitly updated
- Monitoring status or state transitions in systems (online/offline, active/inactive states)
- Displaying step functions in mathematics or control systems
- Showing threshold-based measurements where values only change when crossing specific thresholds
- Tracking employee headcount changes (constant between hire/termination events)
- Visualizing interest rate changes that remain constant between policy updates

---

# Funnel Chart (`funnel`)

## Description

The Funnel Chart visualizes how a metric changes as it progresses through sequential stages, displayed as progressively narrowing horizontal or vertical segments. This chart is powered by Apache ECharts and is useful for tracking conversion rates and identifying drop-off points in multi-stage processes, with each stage's width proportional to its value relative to other stages.

## When to Use

Use a Funnel Chart when you need to visualize sequential stages where values decrease progressively, such as conversion funnels, sales pipelines, or multi-step workflows. This chart type is particularly effective for identifying bottlenecks and drop-off rates between consecutive stages in a process.

## Example Use Cases

- Sales pipeline tracking from leads to closed deals
- E-commerce conversion funnel from product views to purchases
- User onboarding flow completion rates across registration steps
- Marketing campaign performance from impressions to conversions
- Application form completion tracking through multiple steps

---

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

---

# Gauge Chart (`gauge_chart`)

## Description

The Gauge Chart uses a circular gauge visualization to showcase the progress of a metric towards a target value. The position of the dial or progress bar represents the current value, while the gauge axis displays the range from minimum to maximum values. This chart type is built using Apache ECharts and supports customization of angles, intervals, colors, and display options.

## When to Use

Use a Gauge Chart when you need to display a single metric's progress towards a goal or within a defined range. This chart is particularly effective for KPIs, performance metrics, or any measurement where understanding the current value in relation to minimum and maximum thresholds is important. It works best for displaying 1-10 data points simultaneously.

## Example Use Cases

- Displaying sales performance against quarterly targets
- Monitoring server CPU usage within safe operating ranges
- Tracking project completion percentage
- Showing customer satisfaction scores on a scale
- Visualizing equipment temperature or pressure readings with safety thresholds

---

# Graph Chart (`graph_chart`)

## Description

A Graph Chart displays connections between entities in a network structure, visualizing nodes and the relationships (edges) between them. The chart can be configured with either a force-directed layout (where nodes push away from each other) or a circular layout. Nodes can be sized and colored based on their properties, and edges can show directionality with arrows. This chart is ideal for mapping complex relationships and identifying key nodes in a network.

## When to Use

Use a Graph Chart when you need to visualize network relationships, connections, or dependencies between entities. This chart is particularly effective for understanding network topology, identifying central or important nodes, and analyzing the flow or relationships in connected systems.

## Example Use Cases

- Visualizing social network connections and influence patterns
- Mapping organizational hierarchies and reporting relationships
- Analyzing service dependencies in microservices architectures
- Displaying knowledge graphs and concept relationships
- Showing supply chain networks and logistics flows
- Mapping communication patterns between systems or teams

---

# Handlebars (`handlebars`)

## Description

The Handlebars chart type is a highly customizable template-based visualization that allows you to render data using Handlebars templating syntax. It provides the flexibility to create custom HTML layouts with embedded data, enabling you to design unique visualizations beyond standard chart types. The chart supports custom CSS styling and includes built-in Handlebars helpers for common formatting tasks like date formatting, number formatting, and JSON manipulation.

## When to Use

Use the Handlebars chart when you need complete control over the visual presentation of your data, when standard chart types don't meet your specific layout requirements, or when you want to create custom dashboards with branded or highly stylized content. This chart is ideal for users familiar with HTML and Handlebars templating who need to create custom data presentations.

## Example Use Cases

- Custom KPI dashboards with branded layouts and specific styling requirements
- Data reports that need to match existing design systems or corporate templates
- HTML email templates populated with database query results
- Custom data cards or widgets with complex nested structures
- Interactive data lists with custom formatting and conditional styling

---

# Heatmap (`heatmap_v2`)

## Description

The Heatmap visualization uses color intensity to represent metric values across pairs of dimensions. This chart excels at showcasing the correlation or strength between two groups by displaying data in a matrix format where each cell's color represents the magnitude of the metric. Built with Apache ECharts, this visualization provides interactive features and smooth rendering for exploring relationships in your data.

## When to Use

Use a heatmap when you need to visualize the relationship between two categorical dimensions with a quantitative metric. This chart type is particularly effective for identifying patterns, correlations, and outliers across multiple categories. The color-coding makes it easy to spot high and low values at a glance, and normalization options help compare relative values within rows, columns, or across the entire dataset.

## Example Use Cases

- Displaying sales performance across product categories and regions to identify top-performing combinations
- Analyzing website traffic patterns by day of week and hour of day to optimize content publishing schedules
- Visualizing correlation matrices between multiple variables in data science and statistical analysis
- Tracking employee productivity across departments and time periods to identify trends
- Monitoring system performance metrics across different servers and time intervals
- Comparing customer satisfaction scores across service types and demographic segments

---

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

---

# Horizon Chart (`horizon`)

## Description

The Horizon Chart is a time-series visualization that displays how a metric changes over time across different groups. Each group is mapped to its own horizontal row, where change over time is visualized using bar lengths and color intensity. This space-efficient chart type uses layered, mirrored area charts with a shared baseline, allowing you to compare multiple time series in a compact vertical space.

The visualization technique divides the Y-axis into colored bands representing different value ranges. Positive values are shown in one color scheme (typically blues or greens), while negative values use another (typically reds or oranges). By layering these bands and using color intensity to encode magnitude, horizon charts can display many time series in a fraction of the space required by traditional line charts.

## When to Use

Use horizon charts when you need to compare trends across many time series simultaneously in limited vertical space. They are particularly effective when you have 5 or more time series to compare and want to identify patterns, outliers, and correlations across groups. The compact design makes them ideal for dashboards where space is at a premium but detailed trend comparison is essential.

## Example Use Cases

- Monitoring server performance metrics (CPU, memory, network) across dozens of servers in a single view
- Comparing daily sales trends across multiple store locations or product categories over time
- Analyzing stock price movements for a portfolio of securities with limited screen space
- Tracking website traffic patterns across different geographic regions or marketing channels
- Visualizing temperature or weather data trends across multiple weather stations
- Monitoring application error rates or response times across multiple services or endpoints

---

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

---

# Mixed Timeseries (`mixed_timeseries`)

## Description

The Mixed Chart is an advanced time-series visualization that allows you to display two different data series (Query A and Query B) on the same x-axis, each with independent configuration options. This unique capability enables you to combine different chart types (e.g., bars and lines), use separate y-axes (primary and secondary), and apply distinct styling to each series. It's ideal for comparing metrics with different scales or visualizing related but distinct data patterns side by side.

## When to Use

Use the Mixed Chart when you need to compare two different metrics or data series that may have different scales, units, or optimal visualization types. This chart is particularly effective when you want to show correlation, contrast, or complementary relationships between two datasets that share a common time dimension.

## Example Use Cases

- Revenue (bars) vs. profit margin (line) over time to show volume and efficiency together
- Website traffic (line) vs. conversion rate (bars) to correlate visitor volume with success metrics
- Temperature (line on primary y-axis) vs. precipitation (bars on secondary y-axis) for weather analysis
- Sales volume (bars) vs. customer satisfaction score (line) to identify quality-quantity trade-offs
- Inventory levels (line) vs. order quantities (bars) to optimize stock management

---

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

---

# Parallel Coordinates (`para`)

## Description

The Parallel Coordinates chart visualizes multivariate data by plotting individual metrics for each row as vertical axes that are linked together as lines. Each row in the dataset becomes a polyline that traverses across the vertical axes, with the position on each axis representing the value of that metric. This chart is particularly useful for identifying patterns, correlations, and clusters across multiple dimensions simultaneously.

## When to Use

Use this chart type when you need to compare multiple metrics across all samples or rows in your dataset. It excels at revealing relationships between variables and identifying outliers or clusters in multivariate data. The chart is most effective when you have 3-10 metrics to compare, as too many axes can become difficult to interpret.

## Example Use Cases

- Comparing multiple performance indicators (KPIs) across different business units or time periods
- Analyzing product characteristics (price, quality, durability, customer satisfaction) across multiple products
- Evaluating employee metrics (experience, productivity, attendance, satisfaction) across departments
- Studying environmental measurements (temperature, humidity, pressure, pollution levels) across monitoring stations
- Investigating financial ratios (liquidity, profitability, efficiency, leverage) across companies or time periods

---

# Partition Chart (`partition`)

## Description

The Partition Chart visualizes hierarchical data using a space-filling layout where the area of each partition represents the value of a metric. It compares the same summarized metric across multiple groups, showing both the hierarchical relationships and the relative magnitudes of values through partition sizes. The chart supports time series analysis with multiple aggregation options and advanced analytics capabilities.

## When to Use

Use this chart type when you need to display hierarchical categorical data with proportional representation of values. It is particularly effective for showing part-to-whole relationships across multiple dimensions and understanding how values are distributed across categories, especially when comparing time series data or performing temporal analysis.

## Example Use Cases

- Analyzing sales distribution across regions, countries, and cities with revenue shown proportionally
- Visualizing website traffic by traffic source, campaign, and landing page with visitor counts
- Comparing product category performance by department, category, and subcategory with sales metrics
- Examining budget allocation across divisions, departments, and cost centers
- Tracking inventory levels across warehouses, zones, and product categories

---

# Pie Chart (`pie`)

## Description

The Pie Chart visualization displays data as proportional slices of a circular chart, making it ideal for showing how parts contribute to a whole. Built on Apache ECharts, it supports standard pie charts, donut charts, and Nightingale (rose) charts with extensive customization options for labels, legends, and visual appearance.

The classic visualization for showing proportional data. Great for showing how much of a company each investor gets, what demographics follow your blog, or what portion of the budget goes to the military industrial complex.

**Note:** Pie charts can be difficult to interpret precisely. If clarity of relative proportion is important, consider using a bar or other chart type instead.

## When to Use

Use a Pie Chart when you need to:
- Show proportional relationships between categories
- Display percentage breakdowns of a total
- Visualize categorical data with a limited number of segments (typically 5-10)
- Compare parts of a whole at a single point in time
- Create engaging visualizations for presentations or dashboards

## Example Use Cases

- **Financial Analysis**: Visualize budget allocation across departments or spending categories
- **Market Share**: Display competitor distribution in a market segment
- **Demographics**: Show population distribution by age groups, regions, or categories
- **Survey Results**: Present multiple-choice question responses as percentages
- **Resource Allocation**: Illustrate time or resource distribution across projects
- **Portfolio Composition**: Display investment allocation across asset classes

---

# Pivot Table (`pivot_table_v2`)

## Description

The Pivot Table is a tabular visualization that summarizes data by grouping multiple statistics along two axes (rows and columns). It displays aggregated metrics in a grid format where each cell represents the intersection of row and column groupings. The table supports features like subtotals, totals, conditional formatting, and various sorting options, making it ideal for detailed data analysis and reporting.

## When to Use

Use the Pivot Table when you need to compare metrics across multiple dimensions simultaneously, analyze data at various levels of granularity with subtotals, or create comprehensive reports that show relationships between categorical variables. This visualization is particularly valuable when working with multi-dimensional data that requires both row and column hierarchies.

## Example Use Cases

- Sales analysis by region and product category with monthly breakdown
- Employee performance metrics grouped by department and role
- Budget tracking across cost centers and expense types over time
- Customer segmentation showing purchase behavior by age group and location
- Inventory management displaying stock levels by warehouse and product line

---

# Big Number Period Over Period (`pop_kpi`)

## Description

The Big Number with Time Period Comparison chart displays a single metric value prominently along with comparison statistics from a previous time period. It shows the current value, the previous period's value, the absolute change (delta), and the percentage change between periods, making it ideal for tracking KPI performance over time.

## When to Use

Use this chart type when you need to monitor a single key performance indicator and understand how it has changed compared to a previous time period. It is particularly effective for executive dashboards, business reports, and real-time monitoring displays where quick visual assessment of metric trends is essential.

## Example Use Cases

- Monthly revenue tracking with comparison to the previous month
- Daily active users compared to the same day last week or last year
- Sales conversion rates with week-over-week change tracking
- Website traffic metrics compared to the previous time period
- Customer satisfaction scores with period-over-period trend analysis
- Inventory levels with comparison to last quarter
- Operating expenses tracking with year-over-year comparison

---

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

---

# Rose Chart (`rose`)

## Description

The Nightingale Rose Chart (also known as a polar area chart or coxcomb chart) is a polar coordinate visualization where the circle is broken into wedges of equal angle. Each wedge's value is represented by its area rather than its radius or sweep angle. This chart is particularly effective for displaying cyclical data or comparing multiple time series across different categories over time. Named after Florence Nightingale who used this visualization to illustrate mortality causes during the Crimean War, it combines the strengths of pie charts and bar charts while adding a temporal or categorical dimension.

## When to Use

Use this chart when you need to visualize time series data across multiple categories in a circular format that emphasizes cyclical patterns. It's particularly effective when the time dimension has natural periodicity (hourly, daily, weekly, monthly) and you want to compare multiple metrics or categories simultaneously. The rose chart excels at showing both magnitude and temporal patterns, making it ideal for data that repeats over time cycles.

## Example Use Cases

- Analyzing hourly website traffic patterns across different days of the week
- Comparing monthly sales performance across multiple product categories over a year
- Visualizing energy consumption patterns throughout the day across different building zones
- Tracking customer support ticket volumes by hour across different priority levels
- Displaying seasonal revenue patterns across different business units
- Monitoring temperature or weather patterns across months for multiple locations

---

# Sankey Diagram (`sankey_v2`)

## Description

The Sankey Chart visually tracks the movement and transformation of values across system stages. Nodes represent stages, connected by links depicting value flow. Node height corresponds to the visualized metric, providing a clear representation of value distribution and transformation. This chart is powered by Apache ECharts.

## When to Use

Use a Sankey Chart when you need to visualize flows and transformations between different stages or categories in a system. This chart type is particularly effective for showing how quantities are distributed, merged, or split across multiple pathways, making it ideal for understanding value transfers and identifying major flow patterns.

## Example Use Cases

- Visualizing energy or material flows in manufacturing processes
- Tracking budget allocation across departments and projects
- Analyzing website traffic flow between different pages or sections
- Displaying customer journey paths through different touchpoints
- Showing data transfer or network traffic between systems
- Mapping supply chain flows from suppliers to customers
- Analyzing resource consumption and distribution in utilities

---

# Sunburst Chart (`sunburst_v2`)

## Description

The Sunburst Chart visualization uses concentric circles to visualize hierarchical data and the flow of data through different stages of a system. Built on Apache ECharts, it displays multi-level categorical relationships where each ring represents a level in the hierarchy, with the innermost circle representing the top of the hierarchy.

Hover over individual paths in the visualization to understand the stages a value took. This chart type is particularly useful for multi-stage, multi-group visualizing funnels and pipelines, allowing you to see both the hierarchical structure and proportional relationships simultaneously.

## When to Use

Use a Sunburst Chart when you need to:
- Visualize hierarchical data with multiple levels
- Show proportional relationships within a hierarchy
- Display data flow through different stages of a system
- Represent multi-level categorical breakdowns
- Analyze funnel or pipeline data with multiple stages and groups
- Compare both hierarchy and magnitude simultaneously

## Example Use Cases

- **Sales Hierarchies**: Visualize sales data broken down by region > country > product category > product
- **Website Analytics**: Show user journey through website sections > pages > actions with conversion metrics
- **Organizational Structure**: Display company hierarchy with headcount or budget at each level
- **File System Analysis**: Illustrate directory structure with file sizes
- **Process Funnels**: Analyze multi-stage conversion funnels with group segmentation
- **Budget Breakdown**: Show budget allocation from department > team > project > expense category
- **Product Taxonomy**: Display product categories > subcategories > items with sales volumes

---

# Table (`table`)

## Description

The Table chart displays data in a classic row-by-column spreadsheet format. This visualization provides a tabular view of your dataset with extensive customization options including sorting, pagination, search functionality, conditional formatting, and visual enhancements like cell bars. Tables are versatile and can show both raw data records and aggregated metrics, making them suitable for detailed data exploration and reporting.

## When to Use

Use this chart when you need to present data in a structured, readable format that allows users to see individual records or aggregated values in detail. Tables are ideal when precise values matter more than visual patterns, or when you need to present multiple metrics and dimensions together. The table chart supports both aggregate queries (with GROUP BY) and raw data queries, offering flexibility for different analytical needs.

## Example Use Cases

- Displaying detailed sales records with customer information, order amounts, and dates
- Creating executive summary reports with aggregated metrics grouped by region or time period
- Building searchable product catalogs with multiple attributes (name, price, category, stock)
- Showing user activity logs with timestamps, actions, and details
- Presenting comparison tables with metrics across different dimensions using time comparison features
- Creating paginated data browsers for large datasets with server-side pagination
- Displaying financial statements with conditional formatting to highlight positive/negative values

---

# Time Pivot (`time_pivot`)

## Description

The Time-series Period Pivot chart compares metrics between different time periods, displaying time series data across multiple periods (like weeks or months) to show period-over-period trends and patterns. This visualization pivots time data according to a specified frequency, allowing you to see patterns that repeat at regular intervals.

This chart type is built on the NVD3 library and belongs to the "Evolution" category of visualizations.

## When to Use

Use the Time-series Period Pivot chart when you need to:

- Compare metrics across repeating time periods (e.g., compare all Mondays, all first weeks of months)
- Identify cyclical patterns or seasonality in your data
- Analyze period-over-period performance (weekly, monthly, yearly comparisons)
- Visualize time-based aggregations at specific frequencies
- Understand how a metric behaves across different time slices when pivoted by a frequency

## Example Use Cases

- **Weekly Sales Comparison**: Pivot daily sales data by week to compare each Monday across multiple weeks
- **Seasonal Analysis**: Compare metrics across the same day of the week over multiple months
- **Year-over-Year Trends**: Aggregate data at yearly intervals to see long-term patterns
- **Business Cycle Analysis**: Compare metrics at 4-week intervals to align with business reporting cycles
- **Performance Patterns**: Identify recurring performance patterns by pivoting on specific time frequencies

---

# Time Table (`time_table`)

## Description

The Time-series Table visualizes multiple time series metrics side by side in a tabular format, with each row representing either a metric or a grouped column value. Each column in the table can display different types of comparisons including sparklines (inline charts), time-based comparisons, contribution percentages, or period averages. This visualization is ideal for comparing trends and patterns across multiple metrics simultaneously in a compact, information-dense format.

## When to Use

Use this chart type when you need to compare multiple time series metrics or grouped values in a compact table format, display inline sparkline visualizations alongside numerical values, perform time-based comparisons showing changes over periods, or analyze contribution percentages and period averages across multiple dimensions. This visualization excels at providing a comprehensive overview of multiple metrics with their trends in a single view.

## Example Use Cases

- Dashboard KPI summary showing current values, trends (sparklines), and period-over-period changes for key business metrics
- Sales performance comparison across products with revenue sparklines, week-over-week changes, and contribution percentages
- Server monitoring dashboard displaying current metrics with embedded trend charts and time lag comparisons
- Financial reporting showing multiple metrics with their trends, year-over-year comparisons, and percentage contributions
- Marketing campaign performance with engagement metrics, sparkline trends, and comparison to previous periods

---

# Tree Chart (`tree_chart`)

## Description

A Tree Chart visualizes hierarchical data structures using a familiar tree-like layout, showing parent-child relationships between nodes. The chart supports both orthogonal (rectangular) and radial (circular) layouts, with customizable node symbols, labels, and interactive features. Nodes can be sized based on metric values, and the tree can be configured to show different levels of depth. This chart is ideal for displaying organizational structures, file systems, taxonomies, and any data with clear parent-child relationships.

## When to Use

Use a Tree Chart when you need to visualize hierarchical data with a clear parent-child relationship structure. This chart is particularly effective for showing organizational hierarchies, category taxonomies, file system structures, and any data that has a single root node with branching relationships.

## Example Use Cases

- Visualizing organizational charts and reporting structures
- Displaying file system hierarchies and directory structures
- Mapping category taxonomies and classification systems
- Showing decision tree structures and flowcharts
- Analyzing family trees and genealogical relationships
- Displaying product category hierarchies in e-commerce systems

---

# Treemap (treemap_v2)

## Description

The Treemap visualization displays hierarchical relationships of data using nested rectangles, where the area of each rectangle represents a quantitative value. This chart type is ideal for showing proportion and contribution to the whole across multiple levels of categorical data. Treemaps are built using Apache ECharts and support interactive features like drill-down and drill-to-detail operations.

## When to Use

Use a Treemap when you need to:
- Visualize hierarchical data with multiple levels of grouping
- Show proportional relationships where size represents magnitude
- Compare relative sizes of categories and subcategories at a glance
- Identify patterns in nested categorical data
- Display part-to-whole relationships with hierarchical structure
- Present complex data structures in a space-efficient manner

## Example Use Cases

- **Sales Analysis**: Display product sales broken down by category > subcategory > individual products
- **Budget Allocation**: Show organizational budget distribution across departments > teams > expense categories
- **Website Analytics**: Visualize page views by section > page type > individual pages
- **Inventory Management**: Display stock levels organized by warehouse > product category > specific items
- **Market Share Analysis**: Show market share distribution by region > company > product line
- **Resource Utilization**: Visualize compute resource usage by service > instance type > individual instances

---

# Waterfall Chart (`waterfall`)

## Description

The Waterfall Chart is a form of data visualization that helps in understanding the cumulative effect of sequentially introduced positive or negative values. These intermediate values can either be time-based or category-based, displaying how an initial value is affected by a series of positive and negative changes. This chart is powered by Apache ECharts and is particularly effective for visualizing financial data, inventory changes, or any metric that shows incremental changes over time or across categories.

## When to Use

Use a Waterfall Chart when you need to visualize how an initial value is incrementally affected by a series of positive and negative contributions, ultimately reaching a final cumulative total. This chart type excels at showing the sequential impact of increases and decreases, making it easy to identify which factors drive overall change.

## Example Use Cases

- Financial profit and loss analysis showing revenue, expenses, and net profit
- Inventory management tracking stock levels with additions and depletions
- Budget variance analysis comparing planned versus actual spending
- Cash flow statement visualization showing sources and uses of cash
- Project resource allocation showing cumulative time or cost changes across phases

---

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

---

# World Map (`world_map`)

## Description

A map of the world that can indicate values in different countries. This visualization uses choropleth coloring to represent metric values across countries and optionally displays bubbles on top of countries to show additional metrics. The World Map chart is built on [Datamaps](http://datamaps.github.io/) and is part of Superset's legacy chart plugins.

## When to Use

Use the World Map chart when you need to:

- Visualize geographic data at the country level
- Compare metric values across different countries using color intensity
- Show multiple metrics per country (using both country color and bubble size)
- Create interactive geographic visualizations with drill-down capabilities

## Example Use Cases

- **Sales Performance by Country**: Display revenue by country using color intensity, with bubble size representing number of customers
- **Population Metrics**: Show population density with color shading and GDP as bubble size
- **Supply Chain Analysis**: Visualize supplier locations and order volumes across countries
- **COVID-19 Tracking**: Display case counts or vaccination rates by country
- **Customer Distribution**: Show customer concentration across countries with additional revenue metrics
