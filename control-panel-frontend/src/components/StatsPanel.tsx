import type { SimulationStatus } from '../types/api';
import Tooltip from './Tooltip';
import styles from './ControlPanel.module.css';

interface StatsPanelProps {
  status: SimulationStatus;
  driverCount?: number;
  riderCount?: number;
  tripCount?: number;
}

export default function StatsPanel({
  status,
  driverCount,
  riderCount,
  tripCount,
}: StatsPanelProps) {
  // Use real-time counts if provided, otherwise fall back to snapshot counts
  const displayDriverCount = driverCount ?? status.drivers_count;
  const displayRiderCount = riderCount ?? status.riders_count;
  const displayTripCount = tripCount ?? status.active_trips_count;

  return (
    <div className={styles.section}>
      <h3>Statistics</h3>
      <div className={styles.stats}>
        <div className={styles.statItem}>
          <Tooltip text="Total number of driver agents in the simulation">
            <span className={styles.statLabel}>Drivers:</span>
          </Tooltip>
          <span className={styles.statValue}>{displayDriverCount}</span>
        </div>
        <div className={styles.statItem}>
          <Tooltip text="Total number of rider agents requesting rides">
            <span className={styles.statLabel}>Riders:</span>
          </Tooltip>
          <span className={styles.statValue}>{displayRiderCount}</span>
        </div>
        <div className={styles.statItem}>
          <Tooltip text="Number of trips currently in progress">
            <span className={styles.statLabel}>Active Trips:</span>
          </Tooltip>
          <span className={styles.statValue}>{displayTripCount}</span>
        </div>
      </div>
    </div>
  );
}
