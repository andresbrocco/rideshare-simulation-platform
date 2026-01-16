import styles from './Inspector.module.css';

interface InspectorRowProps {
  label: string;
  value: React.ReactNode;
  isId?: boolean;
}

export function InspectorRow({ label, value, isId }: InspectorRowProps) {
  return (
    <div className={styles.row}>
      <span className={styles.label}>{label}:</span>
      <span className={`${styles.value} ${isId ? styles.idValue : ''}`}>{value}</span>
    </div>
  );
}
