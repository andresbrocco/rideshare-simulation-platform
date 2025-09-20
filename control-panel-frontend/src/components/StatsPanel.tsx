import type {
  SimulationStatus,
  DriverMetrics,
  TripMetrics,
  OverviewMetrics,
  RiderMetrics,
} from '../types/api';
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
  riderMetrics?: RiderMetrics | null;
}

export default function StatsPanel({
  status,
  tripCount,
  driverMetrics,
  tripMetrics,
  riderMetrics,
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

  const formatTime = (seconds: number | undefined) => {
    if (seconds === undefined || seconds === null || seconds === 0) return '-';
    if (seconds < 60) return `${Math.round(seconds)}s`;
    return `${(seconds / 60).toFixed(1)} min`;
  };

  return (
    <div className={styles.section}>
      <h3>Statistics</h3>
      <div className={styles.stats}>
        <div className={styles.statsSubsection}>
          <div className={styles.statsSubtitle}>Drivers</div>
          <div className={styles.statsGrid}>
            <div className={styles.statItem}>
              <Tooltip text="Drivers available for new trip requests">
                <span className={styles.statLabel}>Online:</span>
              </Tooltip>
              <span className={styles.statValue}>{driverMetrics?.online ?? '-'}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Drivers not currently active">
                <span className={styles.statLabel}>Offline:</span>
              </Tooltip>
              <span className={styles.statValue}>{driverMetrics?.offline ?? '-'}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Drivers heading to pickup location">
                <span className={styles.statLabel}>To Pickup:</span>
              </Tooltip>
              <span className={styles.statValue}>{driverMetrics?.en_route_pickup ?? '-'}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Drivers heading to dropoff with rider">
                <span className={styles.statLabel}>With Rider:</span>
              </Tooltip>
              <span className={styles.statValue}>{driverMetrics?.en_route_destination ?? '-'}</span>
            </div>
          </div>
        </div>

        <div className={styles.statsSubsection}>
          <div className={styles.statsSubtitle}>Riders</div>
          <div className={styles.statsGrid}>
            <div className={styles.statItem}>
              <Tooltip text="Riders not currently requesting a trip">
                <span className={styles.statLabel}>Offline:</span>
              </Tooltip>
              <span className={styles.statValue}>{riderMetrics?.offline ?? '-'}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Riders waiting for driver to arrive">
                <span className={styles.statLabel}>To Pickup:</span>
              </Tooltip>
              <span className={styles.statValue}>{riderMetrics?.to_pickup ?? '-'}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Riders currently in a vehicle">
                <span className={styles.statLabel}>In Transit:</span>
              </Tooltip>
              <span className={styles.statValue}>{riderMetrics?.in_transit ?? '-'}</span>
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
            <div className={styles.statItem}>
              <Tooltip text="Average time from trip request to driver arrival at pickup">
                <span className={styles.statLabel}>Avg Wait:</span>
              </Tooltip>
              <span className={styles.statValue}>{formatTime(tripMetrics?.avg_wait_seconds)}</span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Average time from match to driver arrival at pickup">
                <span className={styles.statLabel}>Avg Pickup:</span>
              </Tooltip>
              <span className={styles.statValue}>
                {formatTime(tripMetrics?.avg_pickup_seconds)}
              </span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Percentage of offers accepted by drivers">
                <span className={styles.statLabel}>Match Rate:</span>
              </Tooltip>
              <span className={styles.statValue}>
                {tripMetrics?.matching_success_rate !== undefined
                  ? `${tripMetrics.matching_success_rate.toFixed(1)}%`
                  : '-'}
              </span>
            </div>
            <div className={styles.statItem}>
              <Tooltip text="Total offers sent to drivers">
                <span className={styles.statLabel}>Offers Sent:</span>
              </Tooltip>
              <span className={styles.statValue}>{tripMetrics?.offers_sent ?? '-'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
