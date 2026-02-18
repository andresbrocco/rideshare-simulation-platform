import { useState } from 'react';
import type { LayerVisibility } from '../types/layers';
import styles from './LayerControls.module.css';

interface LayerControlsProps {
  visibility: LayerVisibility;
  onChange: (visibility: LayerVisibility) => void;
}

interface LayerConfig {
  key: keyof LayerVisibility;
  label: string;
  color: string;
}

const LAYER_CONFIGS: LayerConfig[] = [
  // Driver layers
  { key: 'onlineDrivers', label: 'Online', color: '#00FF00' },
  { key: 'offlineDrivers', label: 'Offline', color: '#808080' },
  { key: 'enRoutePickupDrivers', label: 'To Pickup', color: '#FFD700' },
  { key: 'withPassengerDrivers', label: 'With Rider', color: '#0000FF' },
  // Rider layers
  { key: 'offlineRiders', label: 'Offline', color: '#C0C0C0' },
  { key: 'waitingRiders', label: 'Waiting', color: '#FFA500' },
  { key: 'matchedRiders', label: 'Matched', color: '#FFD700' },
  { key: 'enRouteRiders', label: 'Driver En Route', color: '#87CEEB' },
  { key: 'arrivedRiders', label: 'Driver Arrived', color: '#00FFFF' },
  { key: 'inTransitRiders', label: 'In Transit', color: '#800080' },
  // Trip/Route layers
  { key: 'pendingRoutes', label: 'Pending Routes', color: '#FFA500' },
  { key: 'pickupRoutes', label: 'Pickup Routes', color: '#FF6496' },
  { key: 'tripRoutes', label: 'Trip Routes', color: '#0064FF' },
  // Zone layers
  { key: 'zoneBoundaries', label: 'Zones', color: '#FFFFFF' },
  { key: 'surgeHeatmap', label: 'Surge', color: '#FFFF00' },
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

  const handleCategoryToggle = (layers: LayerConfig[]) => {
    const keys = layers.map((l) => l.key);
    const allChecked = keys.every((k) => visibility[k]);
    const updates = Object.fromEntries(keys.map((k) => [k, !allChecked]));
    onChange({ ...visibility, ...updates });
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

  const renderSection = (title: string, layers: LayerConfig[]) => {
    const keys = layers.map((l) => l.key);
    const checkedCount = keys.filter((k) => visibility[k]).length;
    const allChecked = checkedCount === keys.length;
    const someChecked = checkedCount > 0 && !allChecked;

    return (
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <input
            type="checkbox"
            ref={(el) => {
              if (el) el.indeterminate = someChecked;
            }}
            checked={allChecked}
            onChange={() => handleCategoryToggle(layers)}
            className={styles.checkbox}
            aria-label={`Toggle all ${title}`}
          />
          <span className={styles.sectionTitle} onClick={() => handleCategoryToggle(layers)}>
            {title}
          </span>
        </div>
        <div className={styles.layerGrid}>
          {layers.map((config) => (
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
    );
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
          {collapsed ? '\u25B2' : '\u25BC'}
        </button>
      </div>

      {!collapsed && (
        <div className={styles.content}>
          {renderSection('Drivers', DRIVER_LAYERS)}
          {renderSection('Riders', RIDER_LAYERS)}
          {renderSection('Routes', ROUTE_LAYERS)}
          {renderSection('Zones', ZONE_LAYERS)}

          <button className={styles.toggleAllButton} onClick={handleToggleAll}>
            Toggle All
          </button>
        </div>
      )}
    </div>
  );
}
