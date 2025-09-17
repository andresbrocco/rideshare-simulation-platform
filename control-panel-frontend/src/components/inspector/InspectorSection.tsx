import styles from './Inspector.module.css';

interface InspectorSectionProps {
  title: string;
  children: React.ReactNode;
}

export function InspectorSection({ title, children }: InspectorSectionProps) {
  return (
    <div className={styles.section}>
      <h4>{title}</h4>
      {children}
    </div>
  );
}
