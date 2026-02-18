import { useEffect, useCallback } from 'react';
import type { PlacementMode } from '../constants/dnaPresets';
import styles from './AgentPlacement.module.css';

interface AgentPlacementProps {
  mode: PlacementMode | null;
  onCancel: () => void;
}

export default function AgentPlacement({ mode, onCancel }: AgentPlacementProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel();
      }
    },
    [onCancel]
  );

  useEffect(() => {
    if (mode) {
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [mode, handleKeyDown]);

  if (!mode) return null;

  const typeLabel = mode.type === 'driver' ? 'Puppet Driver' : 'Puppet Rider';

  return (
    <div className={styles.banner}>
      <div className={styles.content}>
        <span className={styles.icon}>{mode.type === 'driver' ? '🚗' : '👤'}</span>
        <span className={styles.text}>
          Placing <strong>{typeLabel}</strong> - Click on map
        </span>
        <button className={styles.cancelButton} onClick={onCancel} aria-label="Cancel placement">
          ✕
        </button>
      </div>
      <div className={styles.hint}>Press Escape to cancel</div>
    </div>
  );
}
