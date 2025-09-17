import styles from './Inspector.module.css';

interface StatItem {
  value: string | number;
  label: string;
}

interface StatsGridProps {
  stats: StatItem[];
}

export function StatsGrid({ stats }: StatsGridProps) {
  return (
    <div className={styles.statsGrid}>
      {stats.map((stat) => (
        <div key={stat.label} className={styles.statItem}>
          <span className={styles.statValue}>{stat.value}</span>
          <span className={styles.statLabel}>{stat.label}</span>
        </div>
      ))}
    </div>
  );
}
