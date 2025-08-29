import type { SimulationStatus } from '../types/api';
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
          <span className={styles.statLabel}>Drivers:</span>
          <span className={styles.statValue}>{displayDriverCount}</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Riders:</span>
          <span className={styles.statValue}>{displayRiderCount}</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Active Trips:</span>
          <span className={styles.statValue}>{displayTripCount}</span>
        </div>
      </div>
    </div>
  );
}
