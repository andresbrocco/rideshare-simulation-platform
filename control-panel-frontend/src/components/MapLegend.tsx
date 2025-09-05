import styles from './MapLegend.module.css';

const LEGEND_ITEMS = [
  // Driver states
  { id: 'online-drivers', label: 'Online Drivers', color: 'rgb(0, 255, 0)' },
  { id: 'offline-drivers', label: 'Offline Drivers', color: 'rgb(128, 128, 128)' },
  { id: 'en-route-pickup', label: 'En Route to Pickup', color: 'rgb(255, 215, 0)' },
  { id: 'with-passenger', label: 'With Passenger', color: 'rgb(0, 0, 255)' },
  // Rider states (based on trip state)
  { id: 'offline-riders', label: 'Offline', color: 'rgb(192, 192, 192)' },
  { id: 'waiting-riders', label: 'Waiting', color: 'rgb(255, 165, 0)' },
  { id: 'matched-riders', label: 'Matched', color: 'rgb(255, 215, 0)' },
  { id: 'en-route-riders', label: 'Driver En Route', color: 'rgb(135, 206, 235)' },
  { id: 'arrived-riders', label: 'Driver Arrived', color: 'rgb(0, 255, 255)' },
  { id: 'in-transit-riders', label: 'In Transit', color: 'rgb(128, 0, 128)' },
  // Route layers
  { id: 'pending-routes', label: 'Pending Routes', color: 'rgb(255, 165, 0)' },
  { id: 'pickup-routes', label: 'Pickup Routes', color: 'rgb(255, 100, 150)' },
  { id: 'trip-routes', label: 'Trip Routes', color: 'rgb(0, 100, 255)' },
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
