import { useState } from 'react';
import type { LayerVisibility } from '../types/layers';
import styles from './LayerControls.module.css';

interface LayerControlsProps {
  visibility: LayerVisibility;
  onChange: (visibility: LayerVisibility) => void;
}

const LAYER_CONFIGS = [
  // Driver layers
  { key: 'onlineDrivers' as const, label: 'Online', color: '#00FF00' },
  { key: 'offlineDrivers' as const, label: 'Offline', color: '#808080' },
  { key: 'enRoutePickupDrivers' as const, label: 'To Pickup', color: '#FFD700' },
  { key: 'withPassengerDrivers' as const, label: 'With Rider', color: '#0000FF' },
  // Rider layers
  { key: 'offlineRiders' as const, label: 'Offline', color: '#C0C0C0' },
  { key: 'waitingRiders' as const, label: 'Waiting', color: '#FFA500' },
  { key: 'matchedRiders' as const, label: 'Matched', color: '#FFD700' },
  { key: 'enRouteRiders' as const, label: 'Driver En Route', color: '#87CEEB' },
  { key: 'arrivedRiders' as const, label: 'Driver Arrived', color: '#00FFFF' },
  { key: 'inTransitRiders' as const, label: 'In Transit', color: '#800080' },
  // Trip/Route layers
  { key: 'pendingRoutes' as const, label: 'Pending Routes', color: '#FFA500' },
  { key: 'pickupRoutes' as const, label: 'Pickup Routes', color: '#FF6496' },
  { key: 'tripRoutes' as const, label: 'Trip Routes', color: '#0064FF' },
  // Zone layers
  { key: 'zoneBoundaries' as const, label: 'Zones', color: '#FFFFFF' },
  { key: 'surgeHeatmap' as const, label: 'Surge', color: '#FFFF00' },
];

// Group layers by category for better organization
const DRIVER_LAYERS = LAYER_CONFIGS.slice(0, 4);
const RIDER_LAYERS = LAYER_CONFIGS.slice(4, 10);
const ROUTE_LAYERS = LAYER_CONFIGS.slice(10, 13);
const ZONE_LAYERS = LAYER_CONFIGS.slice(13);

export default function LayerControls({ visibility, onChange }: LayerControlsProps) {
  const [collapsed, setCollapsed] = useState(false);

  const handleToggle = (key: keyof LayerVisibility) => {
    onChange({
      ...visibility,
      [key]: !visibility[key],
    });
  };

  const handleToggleAll = () => {
    const anyChecked = Object.values(visibility).some((v) => v);
    const newVisibility = Object.keys(visibility).reduce(
      (acc, key) => ({
        ...acc,
        [key]: !anyChecked,
      }),
      {} as LayerVisibility
    );
    onChange(newVisibility);
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h3 className={styles.title}>Layers</h3>
        <button
          className={styles.collapseButton}
          onClick={() => setCollapsed(!collapsed)}
          aria-label="Collapse"
        >
          {collapsed ? '▲' : '▼'}
        </button>
      </div>

      {!collapsed && (
        <div className={styles.content}>
          {/* Drivers Section */}
          <div className={styles.section}>
            <div className={styles.sectionTitle}>Drivers</div>
            <div className={styles.layerGrid}>
              {DRIVER_LAYERS.map((config) => (
                <label key={config.key} className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={visibility[config.key]}
                    onChange={() => handleToggle(config.key)}
                    className={styles.checkbox}
                  />
                  <span className={styles.colorSwatch} style={{ backgroundColor: config.color }} />
                  <span className={styles.labelText}>{config.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Riders Section */}
          <div className={styles.section}>
            <div className={styles.sectionTitle}>Riders</div>
            <div className={styles.layerGrid}>
              {RIDER_LAYERS.map((config) => (
                <label key={config.key} className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={visibility[config.key]}
                    onChange={() => handleToggle(config.key)}
                    className={styles.checkbox}
                  />
                  <span className={styles.colorSwatch} style={{ backgroundColor: config.color }} />
                  <span className={styles.labelText}>{config.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Routes Section */}
          <div className={styles.section}>
            <div className={styles.sectionTitle}>Routes</div>
            <div className={styles.layerGrid}>
              {ROUTE_LAYERS.map((config) => (
                <label key={config.key} className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={visibility[config.key]}
                    onChange={() => handleToggle(config.key)}
                    className={styles.checkbox}
                  />
                  <span className={styles.colorSwatch} style={{ backgroundColor: config.color }} />
                  <span className={styles.labelText}>{config.label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Zones Section */}
          <div className={styles.section}>
            <div className={styles.sectionTitle}>Zones</div>
            <div className={styles.layerGrid}>
              {ZONE_LAYERS.map((config) => (
                <label key={config.key} className={styles.checkboxLabel}>
                  <input
                    type="checkbox"
                    checked={visibility[config.key]}
                    onChange={() => handleToggle(config.key)}
                    className={styles.checkbox}
                  />
                  <span className={styles.colorSwatch} style={{ backgroundColor: config.color }} />
                  <span className={styles.labelText}>{config.label}</span>
                </label>
              ))}
            </div>
          </div>

          <button className={styles.toggleAllButton} onClick={handleToggleAll}>
            Toggle All
          </button>
        </div>
      )}
    </div>
  );
}
