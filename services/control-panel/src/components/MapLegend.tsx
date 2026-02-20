import { STAGE_CSS } from '../theme';
import styles from './MapLegend.module.css';

const LEGEND_ITEMS = [
  // Driver states
  { id: 'online-drivers', label: 'Available', color: STAGE_CSS.available.base },
  { id: 'offline-drivers', label: 'Offline', color: STAGE_CSS.idle.base },
  { id: 'en-route-pickup', label: 'To Pickup', color: STAGE_CSS.pickup.base },
  { id: 'with-passenger', label: 'On Trip', color: STAGE_CSS.transit.base },
  // Rider states (based on trip state)
  { id: 'offline-riders', label: 'Idle', color: STAGE_CSS.idle.light },
  { id: 'requesting-riders', label: 'Requesting', color: STAGE_CSS.requesting.base },
  { id: 'en-route-riders', label: 'Awaiting Pickup', color: STAGE_CSS.pickup.light },
  { id: 'arrived-riders', label: 'Awaiting Pickup (arrived)', color: STAGE_CSS.pickup.lighter },
  { id: 'in-transit-riders', label: 'In Transit', color: STAGE_CSS.transit.base },
  // Route layers
  { id: 'pending-routes', label: 'Pending Routes', color: STAGE_CSS.requesting.route },
  { id: 'pickup-routes', label: 'Pickup Routes', color: STAGE_CSS.pickup.route },
  { id: 'trip-routes', label: 'Trip Routes', color: STAGE_CSS.transit.route },
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
