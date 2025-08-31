import type { SimulationStatus, DriverMetrics, TripMetrics, OverviewMetrics } from '../types/api';
import Tooltip from './Tooltip';
import styles from './ControlPanel.module.css';

interface StatsPanelProps {
  status: SimulationStatus;
  driverCount?: number;
  riderCount?: number;
  tripCount?: number;
  driverMetrics?: DriverMetrics | null;
  tripMetrics?: TripMetrics | null;
  overviewMetrics?: OverviewMetrics | null;
}

export default function StatsPanel({
  status,
  tripCount,
  driverMetrics,
  tripMetrics,
  overviewMetrics,
}: StatsPanelProps) {
  const displayTripCount = tripCount ?? status.active_trips_count;

  const formatCurrency = (value: number | undefined) => {
    if (value === undefined || value === null) return '-';
    return `R$ ${value.toFixed(2)}`;
  };

  const formatDuration = (value: number | undefined) => {
    if (value === undefined || value === null) return '-';
    return `${value.toFixed(1)} min`;
  };

  return (
    <div className={styles.section}>
      <h3>Statistics</h3>
      <div className={styles.stats}>
        <div className={styles.statsSubsection}>
          <div className={styles.statsSubtitle}>Drivers</div>
          <div className={styles.statsGrid}>
            <div className={styles.statItem}>
              <Tooltip text="Number of drivers currently online and available">
                <span className={styles.statLabel}>Online:</span>
              </Tooltip>
              <span className={styles.statValue}>{driverMetrics?.online ?? '-'}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Number of drivers currently offline">
                <span className={styles.statLabel}>Offline:</span>
              </Tooltip>
              <span className={styles.statValue}>{driverMetrics?.offline ?? '-'}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Number of drivers currently on a trip">
                <span className={styles.statLabel}>Busy:</span>
              </Tooltip>
              <span className={styles.statValue}>{driverMetrics?.busy ?? '-'}</span>
            </div>
          </div>
        </div>

        <div className={styles.statsSubsection}>
          <div className={styles.statsSubtitle}>Riders</div>
          <div className={styles.statsGrid}>
            <div className={styles.statItem}>
              <Tooltip text="Number of riders waiting for a driver">
                <span className={styles.statLabel}>Waiting:</span>
              </Tooltip>
              <span className={styles.statValue}>{overviewMetrics?.waiting_riders ?? '-'}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Number of riders currently in a vehicle">
                <span className={styles.statLabel}>In Transit:</span>
              </Tooltip>
              <span className={styles.statValue}>{overviewMetrics?.in_transit_riders ?? '-'}</span>
            </div>
          </div>
        </div>

        <div className={styles.statsSubsection}>
          <div className={styles.statsSubtitle}>Trips</div>
          <div className={styles.statsGrid}>
            <div className={styles.statItem}>
              <Tooltip text="Number of trips currently in progress">
                <span className={styles.statLabel}>Active:</span>
              </Tooltip>
              <span className={styles.statValue}>{displayTripCount}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Total trips completed today">
                <span className={styles.statLabel}>Completed Today:</span>
              </Tooltip>
              <span className={styles.statValue}>{tripMetrics?.completed_today ?? '-'}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Total trips cancelled today">
                <span className={styles.statLabel}>Cancelled Today:</span>
              </Tooltip>
              <span className={styles.statValue}>{tripMetrics?.cancelled_today ?? '-'}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Average fare for completed trips">
                <span className={styles.statLabel}>Avg Fare:</span>
              </Tooltip>
              <span className={styles.statValue}>{formatCurrency(tripMetrics?.avg_fare)}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Average duration for completed trips">
                <span className={styles.statLabel}>Avg Duration:</span>
              </Tooltip>
              <span className={styles.statValue}>
                {formatDuration(tripMetrics?.avg_duration_minutes)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
