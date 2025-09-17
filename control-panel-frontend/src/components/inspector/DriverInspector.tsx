import type { Driver, DriverState } from '../../types/api';
import { formatTripState } from '../../utils/tripStateFormatter';
import { NextActionsSection } from '../NextActionsSection';
import { InspectorSection } from './InspectorSection';
import { InspectorRow } from './InspectorRow';
import { StatsGrid } from './StatsGrid';
import { DriverActionsSection } from './DriverActionsSection';
import styles from './Inspector.module.css';

interface DriverInspectorProps {
  driver: Driver;
  state: DriverState | null;
  loading: boolean;
  error: string | null;
  actionLoading?: boolean;
  onRefetch: () => void;
  onAcceptOffer?: () => void;
  onRejectOffer?: () => void;
  onArriveAtPickup?: () => void;
  onStartTrip?: () => void;
  onCompleteTrip?: () => void;
  onCancelTrip?: () => void;
  onToggleStatus?: () => void;
}

export function DriverInspector({
  driver,
  state,
  loading,
  error,
  actionLoading = false,
  onAcceptOffer,
  onRejectOffer,
  onArriveAtPickup,
  onStartTrip,
  onCompleteTrip,
  onCancelTrip,
  onToggleStatus,
}: DriverInspectorProps) {
  if (loading) {
    return <div className={styles.loading}>Loading...</div>;
  }

  if (error || !state) {
    return (
      <>
        <h3>Driver</h3>
        <InspectorRow label="ID" value={driver.id} isId />
        <InspectorRow label="Status" value={driver.status} />
        <InspectorRow label="Rating" value={driver.rating} />
        {error && <div className={styles.error}>{error}</div>}
      </>
    );
  }

  const { dna, active_trip, pending_offer, statistics } = state;

  return (
    <>
      <div className={styles.header}>
        <h3>
          {dna.first_name} {dna.last_name}
        </h3>
      </div>
      {state.is_puppet && <span className={styles.badge}>Puppet Driver</span>}

      <InspectorSection title="Status">
        <InspectorRow label="ID" value={driver.id} isId />
        <InspectorRow label="Status" value={state.status} />
        <InspectorRow label="Rating" value={state.current_rating.toFixed(2)} />
        <InspectorRow label="Zone" value={state.zone_id || 'Unknown'} />
      </InspectorSection>

      {pending_offer && (
        <InspectorSection title="Pending Offer">
          <InspectorRow label="Trip ID" value={`${pending_offer.trip_id.slice(0, 8)}...`} />
          <InspectorRow label="Surge" value={`${pending_offer.surge_multiplier.toFixed(1)}x`} />
          <InspectorRow label="Rider Rating" value={pending_offer.rider_rating.toFixed(1)} />
          <InspectorRow label="ETA" value={`${pending_offer.eta_seconds}s`} />
        </InspectorSection>
      )}

      {active_trip && (
        <InspectorSection title="Active Trip">
          {active_trip.counterpart_name && (
            <InspectorRow
              label={
                active_trip.state === 'driver_en_route'
                  ? 'En route to'
                  : active_trip.state === 'driver_arrived'
                    ? 'Waiting for'
                    : active_trip.state === 'started'
                      ? 'Driving'
                      : 'Rider'
              }
              value={active_trip.counterpart_name}
            />
          )}
          <InspectorRow label="State" value={formatTripState(active_trip.state)} />
          <InspectorRow label="Fare" value={`R$ ${active_trip.fare.toFixed(2)}`} />
          <InspectorRow label="Surge" value={`${active_trip.surge_multiplier.toFixed(1)}x`} />
        </InspectorSection>
      )}

      <InspectorSection title="Behavioral DNA">
        <InspectorRow label="Acceptance" value={`${(dna.acceptance_rate * 100).toFixed(0)}%`} />
        <InspectorRow
          label="Service Quality"
          value={`${(dna.service_quality * 100).toFixed(0)}%`}
        />
        <InspectorRow label="Response Time" value={`${dna.response_time.toFixed(1)}s`} />
        <InspectorRow label="Min Rider Rating" value={dna.min_rider_rating.toFixed(1)} />
      </InspectorSection>

      <InspectorSection title="Vehicle">
        <InspectorRow
          label="Vehicle"
          value={`${dna.vehicle_year} ${dna.vehicle_make} ${dna.vehicle_model}`}
        />
        <InspectorRow label="Plate" value={dna.license_plate} />
      </InspectorSection>

      <InspectorSection title="Session Statistics">
        <StatsGrid
          stats={[
            { value: statistics.trips_completed, label: 'Completed' },
            { value: statistics.trips_cancelled, label: 'Cancelled' },
            { value: statistics.offers_received, label: 'Offers' },
            { value: `${statistics.acceptance_rate.toFixed(0)}%`, label: 'Accept Rate' },
          ]}
        />
        <InspectorRow label="Earnings" value={`R$ ${statistics.total_earnings.toFixed(2)}`} />
        {statistics.trips_completed > 0 && (
          <>
            <InspectorRow label="Avg Fare" value={`R$ ${statistics.avg_fare.toFixed(2)}`} />
            <InspectorRow
              label="Avg Pickup"
              value={`${statistics.avg_pickup_time_seconds.toFixed(0)}s`}
            />
            <InspectorRow
              label="Avg Trip"
              value={`${statistics.avg_trip_duration_minutes.toFixed(1)} min`}
            />
          </>
        )}
        {statistics.avg_rating_given > 0 && (
          <InspectorRow label="Avg Rating Given" value={statistics.avg_rating_given.toFixed(1)} />
        )}
      </InspectorSection>

      {state.is_puppet && (
        <InspectorSection title="Actions">
          <DriverActionsSection
            state={state}
            actionLoading={actionLoading}
            onAcceptOffer={onAcceptOffer || (() => {})}
            onRejectOffer={onRejectOffer || (() => {})}
            onArriveAtPickup={onArriveAtPickup || (() => {})}
            onStartTrip={onStartTrip || (() => {})}
            onCompleteTrip={onCompleteTrip || (() => {})}
            onCancelTrip={onCancelTrip || (() => {})}
            onToggleStatus={onToggleStatus || (() => {})}
          />
        </InspectorSection>
      )}

      {!state.is_puppet && <NextActionsSection nextAction={state.next_action} isPuppet={false} />}
    </>
  );
}
