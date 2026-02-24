import type { RiderState } from '../../types/api';
import styles from './Inspector.module.css';

interface RiderActionsSectionProps {
  state: RiderState;
  actionLoading: boolean;
  onRequestTrip: () => void;
  onCancelTrip: () => void;
}

export function RiderActionsSection({
  state,
  actionLoading,
  onRequestTrip,
  onCancelTrip,
}: RiderActionsSectionProps) {
  const { active_trip, status } = state;
  const canCancel = status === 'requesting' || status === 'awaiting_pickup' || status === 'on_trip';

  if (status === 'idle' && !active_trip) {
    return (
      <button className={styles.actionButton} onClick={onRequestTrip} disabled={actionLoading}>
        {actionLoading ? 'Loading...' : 'Request Trip (Select Destination)'}
      </button>
    );
  }

  if (canCancel) {
    return (
      <div className={styles.buttonGroup}>
        <div className={styles.statusBadge}>
          {status === 'requesting'
            ? 'Finding a driver...'
            : status === 'awaiting_pickup'
              ? 'Driver assigned, heading to you...'
              : 'In transit'}
        </div>
        <button
          className={`${styles.actionButton} ${styles.dangerButton}`}
          onClick={onCancelTrip}
          disabled={actionLoading}
        >
          {actionLoading ? 'Loading...' : 'Cancel Trip'}
        </button>
      </div>
    );
  }

  if (!active_trip) {
    return <div className={styles.infoMessage}>Status: {status}</div>;
  }

  return null;
}
