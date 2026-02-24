import { useState } from 'react';
import type { InfrastructureResponse, ServiceMetrics, ContainerStatus } from '../types/api';
import Tooltip from './Tooltip';
import styles from './InfrastructurePanel.module.css';

interface InfrastructurePanelProps {
  data: InfrastructureResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  simulationRealTimeRatio?: number;
}

function formatMemory(mb: number): string {
  if (mb >= 1024) {
    return `${(mb / 1024).toFixed(1)} GB`;
  }
  return `${Math.round(mb)} MB`;
}

function formatLatency(latency_ms: number | null): string {
  if (latency_ms === null) return '-';
  if (latency_ms < 1) return '<1 ms';
  return `${Math.round(latency_ms)} ms`;
}

function getStatusClass(status: ContainerStatus): string {
  switch (status) {
    case 'healthy':
    case 'degraded':
      return styles.statusHealthy; // green — service is responding
    case 'unhealthy':
    case 'stopped':
      return styles.statusUnhealthy; // red — service is unreachable
    default:
      return styles.statusUnknown;
  }
}

function getLatencyClass(
  latency_ms: number | null,
  degraded: number = 100,
  unhealthy: number = 500
): string {
  if (latency_ms === null) return '';
  if (latency_ms < degraded) return styles.latencyGreen;
  if (latency_ms < unhealthy) return styles.latencyOrange;
  return styles.latencyRed;
}

function getRtrClass(rtr: number): string {
  if (rtr >= 0.95) return styles.latencyGreen;
  if (rtr >= 0.8) return styles.latencyOrange;
  return styles.latencyRed;
}

function formatHeartbeatAge(seconds: number | null): string {
  if (seconds === null) return '-';
  if (seconds < 1) return '<1 s';
  return `${Math.round(seconds)} s`;
}

function getHeartbeatAgeClass(
  seconds: number | null,
  degraded: number = 30,
  unhealthy: number = 90
): string {
  if (seconds === null) return '';
  if (seconds < degraded) return styles.latencyGreen;
  if (seconds < unhealthy) return styles.latencyOrange;
  return styles.latencyRed;
}

function getProgressColor(percent: number): string {
  if (percent >= 90) return styles.progressRed;
  if (percent >= 70) return styles.progressOrange;
  return styles.progressGreen;
}

function formatCpuCores(cpuPercent: number, totalCores: number): string {
  return ((cpuPercent * totalCores) / 100).toFixed(2);
}

interface ServiceCardProps {
  service: ServiceMetrics;
  showResources: boolean;
  totalCores: number;
  simulationRealTimeRatio?: number;
}

function ServiceCard({
  service,
  showResources,
  totalCores,
  simulationRealTimeRatio,
}: ServiceCardProps) {
  return (
    <div className={styles.serviceCard}>
      <div className={styles.cardHeader}>
        <span className={styles.serviceName}>{service.name}</span>
        <span className={`${styles.statusIndicator} ${getStatusClass(service.status)}`} />
      </div>

      {simulationRealTimeRatio !== undefined ? (
        <div className={styles.metricRow}>
          <span className={styles.metricLabel}>Real-Time Ratio</span>
          <span className={`${styles.metricValue} ${getRtrClass(simulationRealTimeRatio)}`}>
            {simulationRealTimeRatio.toFixed(2)}
          </span>
        </div>
      ) : service.heartbeat_age_seconds != null ? (
        <div className={styles.metricRow}>
          <span className={styles.metricLabel}>Heartbeat Age</span>
          <span
            className={`${styles.metricValue} ${getHeartbeatAgeClass(service.heartbeat_age_seconds, service.threshold_degraded ?? 30, service.threshold_unhealthy ?? 90)}`}
          >
            {formatHeartbeatAge(service.heartbeat_age_seconds)}
          </span>
        </div>
      ) : service.latency_ms !== null ? (
        <div className={styles.metricRow}>
          <span className={styles.metricLabel}>Latency</span>
          <span
            className={`${styles.metricValue} ${getLatencyClass(service.latency_ms, service.threshold_degraded ?? 100, service.threshold_unhealthy ?? 500)}`}
          >
            {formatLatency(service.latency_ms)}
          </span>
        </div>
      ) : service.message && service.status !== 'unhealthy' && service.status !== 'stopped' ? (
        <div className={styles.metricRow}>
          <span className={styles.metricLabel}>State</span>
          <span className={styles.metricValue}>{service.message}</span>
        </div>
      ) : (
        <div className={styles.metricRow}>
          <span className={styles.metricLabel}>Latency</span>
          <span className={styles.metricValue}>—</span>
        </div>
      )}

      {showResources && (
        <>
          <div className={styles.progressRow}>
            <div className={styles.progressHeader}>
              <span className={styles.progressLabel}>Memory</span>
              <span className={styles.progressValue}>
                {formatMemory(service.memory_used_mb)} / {formatMemory(service.memory_limit_mb)}
              </span>
            </div>
            <div className={styles.progressTrack}>
              <div
                className={`${styles.progressFill} ${getProgressColor(service.memory_percent)}`}
                style={{ width: `${Math.min(service.memory_percent, 100)}%` }}
              />
            </div>
          </div>

          <div className={styles.progressRow}>
            <div className={styles.progressHeader}>
              <span className={styles.progressLabel}>CPU</span>
              <span className={styles.progressValue}>
                {formatCpuCores(service.cpu_percent, totalCores)} / {totalCores} cores
              </span>
            </div>
            <div className={styles.progressBarRow}>
              <div className={styles.progressTrack}>
                <div
                  className={`${styles.progressFill} ${getProgressColor(service.cpu_percent)}`}
                  style={{ width: `${Math.min(service.cpu_percent, 100)}%` }}
                />
              </div>
              <span className={styles.progressPercent}>{service.cpu_percent.toFixed(1)}%</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function InfrastructurePanel({
  data,
  loading,
  error,
  onRefresh,
  simulationRealTimeRatio,
}: InfrastructurePanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  const getOverallStatusClass = (status: ContainerStatus | undefined) => {
    if (status === 'healthy') return styles.overallHealthy;
    return styles.overallUnhealthy;
  };

  const showResources = data?.cadvisor_available ?? false;

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <h3 className={styles.title}>Infrastructure</h3>
          {data && (
            <span
              className={`${styles.overallIndicator} ${getOverallStatusClass(data.overall_status)}`}
            />
          )}
        </div>
        <div className={styles.headerActions}>
          <Tooltip text="Refresh infrastructure metrics">
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
          {error && (
            <div className={styles.errorMessage}>Unable to fetch infrastructure metrics</div>
          )}

          {!showResources && data && (
            <div className={styles.warningMessage}>
              Resource metrics unavailable (cAdvisor not running)
            </div>
          )}

          {data?.discovery_error && (
            <div className={styles.warningMessage}>{data.discovery_error}</div>
          )}

          {/* System Totals */}
          {data && data.cadvisor_available && (
            <div className={styles.totalsSection}>
              <div className={styles.totalsRow}>
                <div className={styles.totalItem}>
                  <Tooltip text="Container usage only. May differ from Activity Monitor which includes Docker VM overhead.">
                    <span className={styles.totalLabel}>Total CPU</span>
                  </Tooltip>
                  <span className={styles.totalValue}>
                    {formatCpuCores(data.total_cpu_percent, data.total_cores)} / {data.total_cores}{' '}
                    cores
                  </span>
                  <div className={styles.progressBarRow}>
                    <div className={styles.progressTrack}>
                      <div
                        className={`${styles.progressFill} ${getProgressColor(data.total_cpu_percent)}`}
                        style={{ width: `${Math.min(data.total_cpu_percent, 100)}%` }}
                      />
                    </div>
                    <span className={styles.progressPercent}>
                      {data.total_cpu_percent.toFixed(1)}%
                    </span>
                  </div>
                </div>
                <div className={styles.totalItem}>
                  <Tooltip text="Container usage only. May differ from Activity Monitor which includes Docker VM overhead.">
                    <span className={styles.totalLabel}>Total Memory</span>
                  </Tooltip>
                  <span className={styles.totalValue}>
                    {formatMemory(data.total_memory_used_mb)} /{' '}
                    {formatMemory(data.total_memory_capacity_mb)}
                  </span>
                  <div className={styles.progressTrack}>
                    <div
                      className={`${styles.progressFill} ${getProgressColor(data.total_memory_percent)}`}
                      style={{ width: `${Math.min(data.total_memory_percent, 100)}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className={styles.serviceGrid}>
            {data?.services.map((service) => (
              <ServiceCard
                key={service.name}
                service={service}
                showResources={showResources}
                totalCores={data?.total_cores ?? 0}
                simulationRealTimeRatio={
                  service.name === 'Simulation' ? simulationRealTimeRatio : undefined
                }
              />
            ))}
          </div>

          {data && (
            <div className={styles.timestamp}>
              Last updated: {new Date(data.timestamp * 1000).toLocaleTimeString()}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
