import type { DriverState } from '../../types/api';
import styles from './Inspector.module.css';

interface DriverActionsSectionProps {
  state: DriverState;
  actionLoading: boolean;
  onAcceptOffer: () => void;
  onRejectOffer: () => void;
  onStartTrip: () => void;
  onCancelTrip: () => void;
  onToggleStatus: () => void;
}

export function DriverActionsSection({
  state,
  actionLoading,
  onAcceptOffer,
  onRejectOffer,
  onStartTrip,
  onCancelTrip,
  onToggleStatus,
}: DriverActionsSectionProps) {
  const { active_trip, pending_offer, status } = state;

  return (
    <>
      {pending_offer && (
        <div className={styles.buttonGroup}>
          {actionLoading ? (
            <button className={styles.actionButton} disabled>
              Loading...
            </button>
          ) : (
            <>
              <button
                className={`${styles.actionButton} ${styles.successButton}`}
                onClick={onAcceptOffer}
              >
                Accept Offer
              </button>
              <button
                className={`${styles.actionButton} ${styles.dangerButton}`}
                onClick={onRejectOffer}
              >
                Reject Offer
              </button>
            </>
          )}
        </div>
      )}

      {active_trip && (
        <div className={styles.buttonGroup}>
          {active_trip.state === 'at_pickup' && (
            <button
              className={`${styles.actionButton} ${styles.successButton}`}
              onClick={onStartTrip}
              disabled={actionLoading}
            >
              {actionLoading ? 'Loading...' : 'Start Trip'}
            </button>
          )}

          {(status === 'en_route_pickup' || status === 'on_trip') && (
            <button
              className={`${styles.actionButton} ${styles.dangerButton}`}
              onClick={onCancelTrip}
              disabled={actionLoading}
            >
              {actionLoading ? 'Loading...' : 'Cancel Trip'}
            </button>
          )}
        </div>
      )}

      {!active_trip && !pending_offer && (
        <button className={styles.actionButton} onClick={onToggleStatus} disabled={actionLoading}>
          {actionLoading ? 'Loading...' : status === 'available' ? 'Go Offline' : 'Go Online'}
        </button>
      )}
    </>
  );
}
