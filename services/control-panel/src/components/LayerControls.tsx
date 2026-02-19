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
  { key: 'onlineDrivers', label: 'Online', color: '#34D399' },
  { key: 'offlineDrivers', label: 'Offline', color: '#6B7280' },
  { key: 'enRoutePickupDrivers', label: 'To Pickup', color: '#F59E0B' },
  { key: 'withPassengerDrivers', label: 'With Rider', color: '#3B82F6' },
  // Rider layers
  { key: 'offlineRiders', label: 'Offline', color: '#9CA3AF' },
  { key: 'requestingRiders', label: 'Requesting', color: '#F97316' },
  { key: 'enRouteRiders', label: 'Driver En Route', color: '#FBBF24' },
  { key: 'arrivedRiders', label: 'Driver Arrived', color: '#FDE047' },
  { key: 'inTransitRiders', label: 'In Transit', color: '#3B82F6' },
  // Trip/Route layers
  { key: 'pendingRoutes', label: 'Pending Routes', color: '#FDBA74' },
  { key: 'pickupRoutes', label: 'Pickup Routes', color: '#FCD34D' },
  { key: 'tripRoutes', label: 'Trip Routes', color: '#60A5FA' },
  // Zone layers
  { key: 'zoneBoundaries', label: 'Zones', color: '#FFFFFF' },
  { key: 'surgeHeatmap', label: 'Surge', color: '#FFFF00' },
];

// Group layers by category for better organization
const DRIVER_LAYERS = LAYER_CONFIGS.slice(0, 4);
const RIDER_LAYERS = LAYER_CONFIGS.slice(4, 9);
const ROUTE_LAYERS = LAYER_CONFIGS.slice(9, 12);
const ZONE_LAYERS = LAYER_CONFIGS.slice(12);

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
