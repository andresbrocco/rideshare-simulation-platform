import type { DriverState } from '../../types/api';
import styles from './Inspector.module.css';

interface DriverActionsSectionProps {
  state: DriverState;
  actionLoading: boolean;
  onAcceptOffer: () => void;
  onRejectOffer: () => void;
  onArriveAtPickup: () => void;
  onStartTrip: () => void;
  onCompleteTrip: () => void;
  onCancelTrip: () => void;
  onToggleStatus: () => void;
}

export function DriverActionsSection({
  state,
  actionLoading,
  onAcceptOffer,
  onRejectOffer,
  onArriveAtPickup,
  onStartTrip,
  onCompleteTrip,
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
          {(status === 'en_route_pickup' || status === 'busy') &&
            active_trip.state !== 'driver_arrived' && (
              <button
                className={styles.actionButton}
                onClick={onArriveAtPickup}
                disabled={actionLoading}
              >
                {actionLoading ? 'Loading...' : 'Arrive at Pickup'}
              </button>
            )}

          {active_trip.state === 'driver_arrived' && (
            <button
              className={`${styles.actionButton} ${styles.successButton}`}
              onClick={onStartTrip}
              disabled={actionLoading}
            >
              {actionLoading ? 'Loading...' : 'Start Trip'}
            </button>
          )}

          {status === 'en_route_destination' && (
            <button
              className={`${styles.actionButton} ${styles.successButton}`}
              onClick={onCompleteTrip}
              disabled={actionLoading}
            >
              {actionLoading ? 'Loading...' : 'Complete Trip'}
            </button>
          )}

          {(status === 'busy' || status === 'en_route_pickup') &&
            active_trip.state !== 'started' && (
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
          {actionLoading ? 'Loading...' : status === 'online' ? 'Go Offline' : 'Go Online'}
        </button>
      )}
    </>
  );
}
