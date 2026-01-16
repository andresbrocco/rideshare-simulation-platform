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
  const canCancel = status === 'waiting' || (active_trip && active_trip.state !== 'started');
  const tripStarted = active_trip?.state === 'started';

  if (status === 'offline' && !active_trip) {
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
          {status === 'waiting' ? 'Waiting for driver...' : 'Trip in progress'}
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

  if (tripStarted) {
    return <div className={styles.infoMessage}>Status: {status}</div>;
  }

  if (status !== 'offline' && status !== 'waiting' && !active_trip) {
    return <div className={styles.infoMessage}>Status: {status}</div>;
  }

  return null;
}
