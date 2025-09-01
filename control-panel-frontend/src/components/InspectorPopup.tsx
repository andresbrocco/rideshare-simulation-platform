import { useMemo } from 'react';
import type { Driver, Rider, ZoneData } from '../types/api';
import styles from './InspectorPopup.module.css';

export type InspectedEntity =
  | { type: 'zone'; data: ZoneData }
  | { type: 'driver'; data: Driver }
  | { type: 'rider'; data: Rider }
  | null;

interface InspectorPopupProps {
  entity: InspectedEntity;
  x: number;
  y: number;
  onClose: () => void;
}

export default function InspectorPopup({ entity, x, y, onClose }: InspectorPopupProps) {
  const { adjustedX, adjustedY } = useMemo(() => {
    const popupWidth = 280;
    const popupHeight = 200;
    const padding = 20;

    let newX = x;
    let newY = y;

    if (x + popupWidth + padding > window.innerWidth) {
      newX = window.innerWidth - popupWidth - padding;
    }
    if (y + popupHeight + padding > window.innerHeight) {
      newY = window.innerHeight - popupHeight - padding;
    }

    return { adjustedX: newX, adjustedY: newY };
  }, [x, y]);

  if (!entity) {
    return null;
  }

  const renderContent = () => {
    if (entity.type === 'zone') {
      const { data } = entity;
      return (
        <>
          <h3>Zone</h3>
          <div className={styles.row}>
            <span className={styles.label}>Name:</span>
            <span className={styles.value}>{data.feature.properties.name}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Surge Multiplier:</span>
            <span className={styles.value}>{data.surge}x</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Drivers:</span>
            <span className={styles.value}>{data.driver_count}</span>
          </div>
        </>
      );
    }

    if (entity.type === 'driver') {
      const { data } = entity;
      return (
        <>
          <h3>Driver</h3>
          <div className={styles.row}>
            <span className={styles.label}>ID:</span>
            <span className={styles.value}>{data.id}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Status:</span>
            <span className={styles.value}>{data.status}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Rating:</span>
            <span className={styles.value}>{data.rating}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Zone:</span>
            <span className={styles.value}>{data.zone}</span>
          </div>
        </>
      );
    }

    if (entity.type === 'rider') {
      const { data } = entity;
      const destinationText =
        data.destination_latitude && data.destination_longitude
          ? `${data.destination_latitude.toFixed(4)}, ${data.destination_longitude.toFixed(4)}`
          : 'Not set';

      return (
        <>
          <h3>Rider</h3>
          <div className={styles.row}>
            <span className={styles.label}>ID:</span>
            <span className={styles.value}>{data.id}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Status:</span>
            <span className={styles.value}>{data.status}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.label}>Destination:</span>
            <span className={styles.value}>{destinationText}</span>
          </div>
        </>
      );
    }

    return null;
  };

  return (
    <div
      className={styles.popup}
      data-testid="inspector-popup"
      style={{
        left: adjustedX,
        top: adjustedY,
      }}
    >
      <button className={styles.closeButton} onClick={onClose} aria-label="Close">
        ×
      </button>
      {renderContent()}
    </div>
  );
}
