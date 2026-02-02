# Superset Dashboards Requirements

This document describes the business intelligence dashboards needed for the Rideshare Simulation Platform. It focuses on **what information** users need to see and **why**, without prescribing specific visualizations or technical implementations.

---

## Overview

The platform requires dashboards that provide visibility into three layers of the data pipeline:

1. **Data Ingestion Health** — Is data flowing correctly from the simulation into storage?
2. **Data Quality** — Is the data valid and trustworthy?
3. **Business Analytics** — What is happening in the rideshare operation?

Users of these dashboards include:
- **Data Engineers** monitoring pipeline health
- **Operations Teams** tracking real-time platform performance
- **Business Analysts** understanding demand patterns and revenue

---

## Dashboard 1: Data Ingestion Monitoring

### Purpose

Data engineers need to monitor whether events from the simulation are being captured correctly. When something breaks in the ingestion pipeline, they need to know immediately and understand where the problem is.

### Questions This Dashboard Should Answer

- **Is data flowing?** How many events have we ingested recently? Is the volume what we expect?
- **Are all data sources healthy?** Are we receiving data from all expected sources (trips, GPS pings, driver updates, payments, etc.)? Is any source missing or lagging?
- **Are there errors?** How many events failed to process? What kinds of errors are we seeing?
- **Is there delay?** How long does it take for an event to go from the simulation to our storage?
- **Is load distributed?** Are events spread evenly across processing partitions, or is one partition overloaded?

### Information Needed

1. **Total ingestion volume** — A single number showing how many events were ingested in the last 24 hours, so engineers can quickly see if ingestion is working at expected scale.

2. **Volume by data source** — A breakdown showing how many events came from each source (trips, GPS, driver status, etc.). This helps identify if a specific source stopped sending data.

3. **Ingestion over time** — A trend showing how ingestion volume changes hour by hour. Sudden drops indicate problems; the pattern also shows normal daily cycles.

4. **Error count** — How many events went to the dead letter queue (failed processing). This should be zero or very low in healthy operation.

5. **Errors by type** — When errors exist, what categories are they? This helps engineers diagnose whether it's a schema issue, connectivity problem, or something else.

6. **Processing distribution** — How events are spread across processing workers/partitions. Uneven distribution can cause bottlenecks.

7. **Data freshness by source** — For each data source, when was the last event received? This immediately shows if a source has gone silent.

8. **Ingestion delay** — The maximum time between when an event occurred and when it was stored. High delay indicates pipeline backlog.

---

## Dashboard 2: Data Quality Monitoring

### Purpose

Before data can be used for analytics, it must be validated. This dashboard shows the results of data quality checks, helping engineers identify bad data before it pollutes downstream reports.

### Questions This Dashboard Should Answer

- **How much bad data exists?** What's the overall volume of detected anomalies?
- **What types of problems are we seeing?** Are they GPS errors, impossible values, stale records?
- **Is data quality improving or degrading?** Are anomaly rates going up or down over time?
- **Which staging tables have data?** Are all expected tables populated?
- **Is processed data fresh?** When was each table last updated?

### Information Needed

1. **Total anomalies** — A single number showing how many data quality issues were detected recently. Should be low relative to total volume.

2. **Anomalies by category** — A breakdown of what types of issues were found. Categories include:
   - GPS outliers (coordinates outside the expected geographic area)
   - Impossible speeds (calculated velocities that exceed physical possibility)
   - Zombie drivers (drivers marked as active but not sending location updates)
   - Other validation failures

3. **Anomaly trend** — How the number of detected anomalies changes over time. A sudden spike indicates a new data problem.

4. **GPS outlier count** — Specifically how many location points fell outside the expected São Paulo boundaries. High numbers suggest GPS spoofing or device issues.

5. **Impossible speed count** — How many calculated speeds exceeded reasonable limits (e.g., over 200 km/h). Indicates timestamp or location errors.

6. **Stale driver list** — A list of specific drivers who appear active but haven't sent GPS updates for an extended period. These need investigation.

7. **Table row counts** — For each staging table, how many records exist. Shows whether data is flowing through the pipeline to all expected destinations.

8. **Table freshness** — When each staging table was last updated. Stale tables indicate pipeline failures.

---

## Dashboard 3: Platform Operations

### Purpose

Operations teams need a real-time view of what's happening on the rideshare platform right now. This dashboard answers "Is the platform healthy?" at a glance.

### Questions This Dashboard Should Answer

- **What's happening right now?** How many trips are in progress?
- **How has today been?** How many trips completed? What's the total revenue?
- **Are riders waiting too long?** What's the average time from match to pickup?
- **Are there processing issues?** Are pipeline errors affecting operations?
- **What's the throughput?** How many trips are completing per hour?
- **Where is activity concentrated?** Which areas of the city have the most trips?

### Information Needed

1. **Active trips** — How many trips are currently in progress (rider is in vehicle or driver is en route). This is the platform's "pulse."

2. **Completed trips today** — Total trips that finished today. Indicates overall platform activity level.

3. **Average wait time** — The typical time riders wait from being matched to being picked up. A key service quality metric.

4. **Revenue today** — Total fares collected from completed trips. The primary business metric.

5. **Recent errors** — Any processing errors in the last hour that might affect operations. Operations teams need to know if data is unreliable.

6. **Errors by category** — If errors exist, what types? Helps determine if action is needed.

7. **Hourly trip volume** — How trip completions vary throughout the day. Shows demand patterns and helps identify unusual activity.

8. **Processing delay** — How long it takes for completed trip data to become available. High delay means dashboards show stale information.

9. **Geographic distribution** — Which zones or neighborhoods have the most trip activity today. Helps understand where demand is concentrated.

---

## Dashboard 4: Driver Performance

### Purpose

Understanding driver behavior and performance helps optimize the driver network. This dashboard helps identify top performers, understand driver economics, and spot potential issues.

### Questions This Dashboard Should Answer

- **Who are the best performers?** Which drivers complete the most trips?
- **How are drivers rated?** What's the distribution of driver ratings?
- **How much are drivers earning?** What are payout trends over time?
- **How efficiently are drivers working?** What portion of their online time is spent on trips?
- **Is there a relationship between trips and earnings?** Do more trips always mean more money?
- **How many drivers are active?** What's the driver supply situation?

### Information Needed

1. **Top drivers** — A ranking of drivers who completed the most trips today. Identifies high performers.

2. **Rating distribution** — How driver ratings are spread across the rating scale. Are most drivers highly rated, or is there a wide spread?

3. **Payout trends** — How total driver payouts have changed over recent days. Shows whether driver earnings are growing or declining.

4. **Utilization patterns** — For each driver, what percentage of their online time was spent on trips. Low utilization might indicate oversupply in certain areas.

5. **Trips vs. earnings** — The relationship between how many trips a driver completes and how much they earn. Helps understand if the incentive structure is working.

6. **Driver activity status** — How many drivers are currently active. Basic supply metric.

---

## Dashboard 5: Demand Analysis

### Purpose

Understanding where and when demand occurs helps with driver positioning, surge pricing, and capacity planning. This dashboard reveals demand patterns across time and geography.

### Questions This Dashboard Should Answer

- **Where is demand highest?** Which zones have the most trip requests?
- **How does demand change over time?** What are the hourly patterns?
- **Is surge pricing active?** Where and when are prices elevated?
- **How long are riders waiting?** Does wait time vary by zone?
- **What are the peak demand zones?** Where should we focus driver supply?
- **When do surge events occur?** What triggers elevated pricing?

### Information Needed

1. **Demand by zone and time** — A view showing how demand intensity varies across different zones and time periods. Reveals hot spots.

2. **Surge pricing trends** — How the average surge multiplier changes over time. Shows when prices are elevated platform-wide.

3. **Wait time by zone** — Average rider wait time in each zone. High wait times indicate undersupply.

4. **Hourly demand pattern** — The typical demand curve throughout the day. Shows morning rush, evening rush, and quiet periods.

5. **Top demand zones** — A ranking of zones by trip request volume. Identifies where to focus driver recruitment/positioning.

6. **Surge event history** — When and where surge pricing was triggered. Helps understand what conditions cause price increases.

---

## Dashboard 6: Revenue Analytics

### Purpose

Business leadership needs to understand the financial performance of the platform. This dashboard provides revenue metrics, fee collection, and economic breakdowns.

### Questions This Dashboard Should Answer

- **How much revenue today?** What's the total fare collection?
- **How much does the platform earn?** What are total platform fees?
- **How many trips generated this revenue?** What's the trip volume?
- **Which zones generate the most revenue?** Where is money being made?
- **Is revenue growing?** What's the trend over recent days?
- **How do fares relate to distance?** Is pricing working as expected?
- **How do riders pay?** What's the payment method mix?
- **When is revenue highest?** What times of day generate the most money?
- **Which zones are most valuable?** Where should we invest in growth?

### Information Needed

1. **Daily revenue** — Total fares collected today. The headline number for business health.

2. **Platform fees** — Total fees the platform retained from fares today. The actual platform revenue.

3. **Trip count** — Number of completed paid trips today. Volume metric.

4. **Revenue by zone** — Which zones contributed the most to today's revenue. Geographic revenue distribution.

5. **Revenue trend** — How daily revenue has changed over the past week. Shows growth or decline.

6. **Fare vs. distance** — The relationship between trip distance and fare charged. Validates that pricing is working correctly.

7. **Payment method mix** — Distribution of payment methods used (credit card, cash, etc.). Important for payment processing planning.

8. **Revenue by time of day** — How revenue varies by hour. Identifies high-value time periods.

9. **Top revenue zones** — Ranking of zones by total revenue over a longer period. Strategic planning input.

---

## Infrastructure Requirements

### Database Connection

The dashboards need to connect to the data lakehouse via Spark. This connection should be:
- Automatically configured when the analytics service starts
- Available in the SQL exploration interface for ad-hoc queries
- Able to query all three data layers (bronze, silver, gold)

### Refresh Behavior

Dashboards should refresh automatically at a reasonable interval (e.g., every few minutes) so users see near-real-time data without manual refresh.

### Access

- Dashboards should be accessible via web browser
- Default credentials should work for development
- Production deployments must change default credentials

---

## Data Layer Mapping

For reference, here's which data layer each dashboard primarily uses:

| Dashboard | Primary Data Layer | Notes |
|-----------|-------------------|-------|
| Data Ingestion Monitoring | Bronze | Raw ingested events |
| Data Quality Monitoring | Silver | Validated/cleaned data |
| Platform Operations | Gold | Business-ready aggregates |
| Driver Performance | Gold | Driver-focused aggregates |
| Demand Analysis | Gold | Zone and time aggregates |
| Revenue Analytics | Gold | Financial aggregates |

---

## Summary

| Dashboard | Primary User | Key Question |
|-----------|--------------|--------------|
| Data Ingestion Monitoring | Data Engineer | "Is data flowing correctly?" |
| Data Quality Monitoring | Data Engineer | "Is the data trustworthy?" |
| Platform Operations | Operations Team | "Is the platform healthy right now?" |
| Driver Performance | Operations/Business | "How are drivers performing?" |
| Demand Analysis | Business Analyst | "Where and when is demand?" |
| Revenue Analytics | Business Leadership | "How is the business doing financially?" |

**Total: 6 dashboards serving 3 user personas across 3 data layers**
