import { useState } from 'react';
import type { InfrastructureResponse, ServiceMetrics, ContainerStatus } from '../types/api';
import Tooltip from './Tooltip';
import styles from './InfrastructurePanel.module.css';

interface InfrastructurePanelProps {
  data: InfrastructureResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
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
      return styles.statusHealthy;
    case 'degraded':
      return styles.statusDegraded;
    case 'unhealthy':
      return styles.statusUnhealthy;
    case 'stopped':
      return styles.statusStopped;
    default:
      return styles.statusUnknown;
  }
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
}

function ServiceCard({ service, showResources, totalCores }: ServiceCardProps) {
  return (
    <div className={styles.serviceCard}>
      <div className={styles.cardHeader}>
        <span className={styles.serviceName}>{service.name}</span>
        <Tooltip text={service.message || service.status}>
          <span className={`${styles.statusIndicator} ${getStatusClass(service.status)}`} />
        </Tooltip>
      </div>

      <div className={styles.metricRow}>
        <span className={styles.metricLabel}>Latency</span>
        <span className={styles.metricValue}>{formatLatency(service.latency_ms)}</span>
      </div>

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
}: InfrastructurePanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  const getOverallStatusClass = (status: ContainerStatus | undefined) => {
    switch (status) {
      case 'healthy':
        return styles.overallHealthy;
      case 'degraded':
        return styles.overallDegraded;
      case 'unhealthy':
        return styles.overallUnhealthy;
      case 'stopped':
        return styles.overallStopped;
      default:
        return styles.overallUnknown;
    }
  };

  const showResources = data?.cadvisor_available ?? false;

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <h3 className={styles.title}>Infrastructure</h3>
          {data && (
            <Tooltip text={`Overall: ${data.overall_status}`}>
              <span
                className={`${styles.overallIndicator} ${getOverallStatusClass(data.overall_status)}`}
              />
            </Tooltip>
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
