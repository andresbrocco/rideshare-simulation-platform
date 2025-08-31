import { useState } from 'react';
import type { LayerVisibility } from '../types/layers';
import MapLegend from './MapLegend';
import styles from './LayerControls.module.css';

interface LayerControlsProps {
  visibility: LayerVisibility;
  onChange: (visibility: LayerVisibility) => void;
}

const LAYER_CONFIGS = [
  { key: 'onlineDrivers' as const, label: 'Online Drivers' },
  { key: 'offlineDrivers' as const, label: 'Offline Drivers' },
  { key: 'busyDrivers' as const, label: 'Busy Drivers' },
  { key: 'waitingRiders' as const, label: 'Waiting Riders' },
  { key: 'inTransitRiders' as const, label: 'In-Transit Riders' },
  { key: 'tripRoutes' as const, label: 'Trip Routes' },
  { key: 'gpsTrails' as const, label: 'GPS Trails' },
  { key: 'zoneBoundaries' as const, label: 'Zone Boundaries' },
  { key: 'surgeHeatmap' as const, label: 'Surge Heatmap' },
];

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
          <div className={styles.controls}>
            {LAYER_CONFIGS.map((config) => (
              <label key={config.key} className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={visibility[config.key]}
                  onChange={() => handleToggle(config.key)}
                  className={styles.checkbox}
                />
                <span>{config.label}</span>
              </label>
            ))}
          </div>

          <button className={styles.toggleAllButton} onClick={handleToggleAll}>
            Toggle All
          </button>

          <MapLegend />
        </div>
      )}
    </div>
  );
}
