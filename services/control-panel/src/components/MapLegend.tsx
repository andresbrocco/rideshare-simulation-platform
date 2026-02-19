import styles from './MapLegend.module.css';

const LEGEND_ITEMS = [
  // Driver states
  { id: 'online-drivers', label: 'Online Drivers', color: 'rgb(52, 211, 153)' },
  { id: 'offline-drivers', label: 'Offline Drivers', color: 'rgb(107, 114, 128)' },
  { id: 'en-route-pickup', label: 'En Route to Pickup', color: 'rgb(245, 158, 11)' },
  { id: 'with-passenger', label: 'With Passenger', color: 'rgb(59, 130, 246)' },
  // Rider states (based on trip state)
  { id: 'offline-riders', label: 'Offline', color: 'rgb(156, 163, 175)' },
  { id: 'requesting-riders', label: 'Requesting', color: 'rgb(249, 115, 22)' },
  { id: 'en-route-riders', label: 'Driver En Route', color: 'rgb(251, 191, 36)' },
  { id: 'arrived-riders', label: 'Driver Arrived', color: 'rgb(253, 224, 71)' },
  { id: 'in-transit-riders', label: 'In Transit', color: 'rgb(59, 130, 246)' },
  // Route layers
  { id: 'pending-routes', label: 'Pending Routes', color: 'rgb(253, 186, 116)' },
  { id: 'pickup-routes', label: 'Pickup Routes', color: 'rgb(252, 211, 77)' },
  { id: 'trip-routes', label: 'Trip Routes', color: 'rgb(96, 165, 250)' },
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
