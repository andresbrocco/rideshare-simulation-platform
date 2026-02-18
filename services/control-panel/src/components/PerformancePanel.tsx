import { useState } from 'react';
import type { PerformanceMetrics, FrontendMetrics, LatencyMetrics, ErrorStats } from '../types/api';
import Tooltip from './Tooltip';
import styles from './PerformancePanel.module.css';

interface PerformancePanelProps {
  metrics: PerformanceMetrics | null;
  frontendMetrics: FrontendMetrics;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

function formatNumber(value: number, decimals: number = 0): string {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}k`;
  }
  return value.toFixed(decimals);
}

function formatLatency(latency: LatencyMetrics | null): string {
  if (!latency || latency.count === 0) return '-';
  return `${latency.avg_ms.toFixed(2)}ms / ${latency.p95_ms.toFixed(2)}ms`;
}

function formatErrorRate(errors: ErrorStats | null): string {
  if (!errors || errors.count === 0) return '-';
  return `${errors.per_second.toFixed(1)}/s (${errors.count})`;
}

function hasErrors(metrics: PerformanceMetrics | null): boolean {
  if (!metrics?.errors) return false;
  return (
    (metrics.errors.osrm?.count ?? 0) > 0 ||
    (metrics.errors.kafka?.count ?? 0) > 0 ||
    (metrics.errors.redis?.count ?? 0) > 0
  );
}

interface MetricRowProps {
  label: string;
  value: string;
  tooltip?: string;
  highlight?: boolean;
}

function MetricRow({ label, value, tooltip, highlight }: MetricRowProps) {
  return (
    <div className={`${styles.metricRow} ${highlight ? styles.highlight : ''}`}>
      {tooltip ? (
        <Tooltip text={tooltip}>
          <span className={styles.metricLabel}>{label}</span>
        </Tooltip>
      ) : (
        <span className={styles.metricLabel}>{label}</span>
      )}
      <span className={styles.metricValue}>{value}</span>
    </div>
  );
}

export default function PerformancePanel({
  metrics,
  frontendMetrics,
  loading,
  error,
  onRefresh,
}: PerformancePanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <h3 className={styles.title}>Performance</h3>
          {metrics && (
            <span className={styles.totalEvents}>
              {formatNumber(metrics.events.total_per_sec, 3)}/s
            </span>
          )}
        </div>
        <div className={styles.headerActions}>
          <Tooltip text="Refresh metrics">
            <button
              className={styles.refreshButton}
              onClick={onRefresh}
              disabled={loading}
              aria-label="Refresh"
            >
              {loading ? '...' : '\u21bb'}
            </button>
          </Tooltip>
          <button
            className={styles.collapseButton}
            onClick={() => setCollapsed(!collapsed)}
            aria-label={collapsed ? 'Expand' : 'Collapse'}
          >
            {collapsed ? '\u25b2' : '\u25bc'}
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className={styles.content}>
          {error && <div className={styles.errorMessage}>Unable to fetch metrics</div>}

          <div className={styles.section}>
            <div className={styles.sectionTitle}>Events/sec</div>
            <MetricRow
              label="GPS Pings"
              value={metrics ? formatNumber(metrics.events.gps_pings_per_sec, 3) : '-'}
              tooltip="GPS location updates from drivers and riders"
            />
            <MetricRow
              label="Trip Events"
              value={metrics ? formatNumber(metrics.events.trip_events_per_sec, 3) : '-'}
              tooltip="Trip state changes (requested, matched, completed, etc.)"
            />
            <MetricRow
              label="Driver Status"
              value={metrics ? formatNumber(metrics.events.driver_status_per_sec, 3) : '-'}
              tooltip="Driver availability status changes"
            />
          </div>

          <div className={styles.section}>
            <div className={styles.sectionTitle}>Latency (avg / p95)</div>
            <MetricRow
              label="OSRM"
              value={metrics ? formatLatency(metrics.latency.osrm) : '-'}
              tooltip="Routing service response time"
              highlight={metrics?.latency.osrm && metrics.latency.osrm.avg_ms > 100 ? true : false}
            />
            <MetricRow
              label="Kafka"
              value={metrics ? formatLatency(metrics.latency.kafka) : '-'}
              tooltip="Event publishing latency"
            />
          </div>

          {hasErrors(metrics) && (
            <div className={styles.section}>
              <div className={styles.sectionTitle}>Errors</div>
              {metrics?.errors.osrm && metrics.errors.osrm.count > 0 && (
                <MetricRow
                  label="OSRM"
                  value={formatErrorRate(metrics.errors.osrm)}
                  tooltip="OSRM routing errors"
                  highlight
                />
              )}
              {metrics?.errors.kafka && metrics.errors.kafka.count > 0 && (
                <MetricRow
                  label="Kafka"
                  value={formatErrorRate(metrics.errors.kafka)}
                  tooltip="Kafka publishing errors"
                  highlight
                />
              )}
              {metrics?.errors.redis && metrics.errors.redis.count > 0 && (
                <MetricRow
                  label="Redis"
                  value={formatErrorRate(metrics.errors.redis)}
                  tooltip="Redis pub/sub errors"
                  highlight
                />
              )}
            </div>
          )}

          <div className={styles.section}>
            <div className={styles.sectionTitle}>Simulation Engine</div>
            <MetricRow
              label="Threads"
              value={metrics?.resources ? metrics.resources.thread_count.toString() : '-'}
              tooltip="Active Python threads in simulation process"
            />
            <MetricRow
              label="SimPy Queue"
              value={metrics ? formatNumber(metrics.queue_depths.simpy_events) : '-'}
              tooltip="Pending simulation events in the discrete event queue"
            />
          </div>

          {metrics?.stream_processor && (
            <div className={styles.section}>
              <div className={styles.sectionTitle}>Stream Processor</div>
              <MetricRow
                label="Consume"
                value={`${formatNumber(metrics.stream_processor.messages_consumed_per_sec, 3)}/s`}
                tooltip="Messages consumed from Kafka per second"
              />
              <MetricRow
                label="Publish"
                value={`${formatNumber(metrics.stream_processor.messages_published_per_sec, 3)}/s`}
                tooltip="Messages published to Redis per second"
              />
              <MetricRow
                label="GPS Reduction"
                value={
                  metrics.stream_processor.gps_aggregation_ratio > 0
                    ? `${metrics.stream_processor.gps_aggregation_ratio.toFixed(1)}x`
                    : '-'
                }
                tooltip="GPS message reduction ratio (higher = more aggregation)"
              />
              <MetricRow
                label="Redis Latency"
                value={
                  metrics.stream_processor.redis_publish_latency.count > 0
                    ? `${metrics.stream_processor.redis_publish_latency.avg_ms.toFixed(2)}ms / ${metrics.stream_processor.redis_publish_latency.p95_ms.toFixed(2)}ms`
                    : '-'
                }
                tooltip="Redis publish latency (avg / p95)"
                highlight={metrics.stream_processor.redis_publish_latency.avg_ms > 50}
              />
              {metrics.stream_processor.publish_errors_per_sec > 0 && (
                <MetricRow
                  label="Errors"
                  value={`${metrics.stream_processor.publish_errors_per_sec.toFixed(1)}/s`}
                  tooltip="Redis publish errors per second"
                  highlight
                />
              )}
            </div>
          )}

          <div className={styles.section}>
            <div className={styles.sectionTitle}>Frontend</div>
            <MetricRow
              label="WS Messages"
              value={`${formatNumber(frontendMetrics.ws_messages_per_sec, 3)}/s`}
              tooltip="WebSocket messages received per second"
            />
            <MetricRow
              label="Render FPS"
              value={frontendMetrics.render_fps.toString()}
              tooltip="Browser render frame rate"
              highlight={frontendMetrics.render_fps < 30}
            />
          </div>
        </div>
      )}
    </div>
  );
}
