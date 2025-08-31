import styles from './MapLegend.module.css';

const LEGEND_ITEMS = [
  { id: 'online-drivers', label: 'Online Drivers', color: 'rgb(0, 255, 0)' },
  { id: 'offline-drivers', label: 'Offline Drivers', color: 'rgb(128, 128, 128)' },
  { id: 'busy-drivers', label: 'Busy Drivers', color: 'rgb(0, 0, 255)' },
  { id: 'waiting-riders', label: 'Waiting Riders', color: 'rgb(255, 165, 0)' },
  { id: 'in-transit-riders', label: 'In-Transit Riders (In Transit)', color: 'rgb(128, 0, 128)' },
  { id: 'trip-routes', label: 'Trip Routes', color: 'rgb(0, 200, 255)' },
  { id: 'gps-trails', label: 'GPS Trails', color: 'rgb(255, 100, 100)' },
  { id: 'zone-boundaries', label: 'Zone Boundaries', color: 'rgb(255, 255, 255)' },
  { id: 'surge-heatmap', label: 'Surge Heatmap', color: 'rgb(255, 255, 0)' },
];

export default function MapLegend() {
  return (
    <div className={styles.legend}>
      <h3 className={styles.title}>Legend</h3>
      <ul className={styles.list}>
        {LEGEND_ITEMS.map((item) => (
          <li key={item.id} className={styles.item}>
            <span
              className={styles.swatch}
              style={{ backgroundColor: item.color }}
              data-testid={`swatch-${item.id}`}
            />
            <span className={styles.label}>{item.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
