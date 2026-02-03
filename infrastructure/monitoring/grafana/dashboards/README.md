# Grafana Dashboards

This directory contains Grafana dashboard definitions that are auto-provisioned on startup.

## Available Dashboards

### simulation-metrics.json

The main simulation monitoring dashboard with 6 rows of panels:

1. **Business Overview** - Drivers online, riders in transit, active trips, matching success rate
2. **Trip Quality Metrics** - Average fare, duration, wait time, pickup time
3. **Event Throughput** - Events/sec by type, total throughput, queue depths
4. **Latency Histograms** - OSRM, Kafka, and Redis latency percentiles (p50, p95, p99)
5. **Errors & Health** - Error rates by component, stream processor connection status
6. **Resource Monitoring** - Container memory and CPU usage (via cAdvisor)

## Adding New Dashboards

### Kafka Monitoring

To add Kafka-specific metrics (beyond cAdvisor container metrics), deploy [kafka-exporter](https://github.com/danielqsj/kafka_exporter):

```yaml
# Add to docker-compose.yml
kafka-exporter:
  image: danielqsj/kafka-exporter:latest
  command:
    - --kafka.server=kafka:9092
  ports:
    - "9308:9308"
```

Then add to `prometheus.yml`:

```yaml
- job_name: 'kafka-exporter'
  static_configs:
    - targets: ['kafka-exporter:9308']
```

Metrics available: `kafka_consumergroup_lag`, `kafka_topic_partitions`, `kafka_brokers`, etc.

### Spark Monitoring

To add Spark metrics, configure the JMX exporter in Spark:

```yaml
# Add to Spark container environment
SPARK_DRIVER_EXTRAJAVAOPTIONS: -javaagent:/opt/jmx_exporter.jar=7072:/opt/spark-metrics.yaml
```

See [Spark Metrics Configuration](https://spark.apache.org/docs/latest/monitoring.html).

### Airflow Monitoring

To add Airflow metrics, deploy [airflow-exporter](https://github.com/epoch8/airflow-exporter):

```yaml
airflow-exporter:
  image: pbweb/airflow-prometheus-exporter:latest
  environment:
    - AIRFLOW_PROMETHEUS_LISTEN_ADDR=:9112
    - AIRFLOW_PROMETHEUS_DATABASE_URI=postgresql://...
  ports:
    - "9112:9112"
```

Alternatively, use the built-in StatsD exporter by setting `AIRFLOW__SCHEDULER__STATSD_ON=True`.

## Dashboard Variables

All dashboards use the `${DS_PROMETHEUS}` variable for the Prometheus datasource UID, allowing them to work across environments without hardcoded values.
