import type { SimulationStatus } from '../types/api';
import styles from './ControlPanel.module.css';

interface StatsPanelProps {
  status: SimulationStatus;
}

export default function StatsPanel({ status }: StatsPanelProps) {
  return (
    <div className={styles.section}>
      <h3>Statistics</h3>
      <div className={styles.stats}>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Drivers:</span>
          <span className={styles.statValue}>{status.drivers_count}</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Riders:</span>
          <span className={styles.statValue}>{status.riders_count}</span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statLabel}>Active Trips:</span>
          <span className={styles.statValue}>{status.active_trips_count}</span>
        </div>
      </div>
    </div>
  );
}
