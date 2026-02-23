import type { Driver, DriverState } from '../../types/api';
import { formatTripState } from '../../utils/tripStateFormatter';
import { formatDriverStatus } from '../../utils/driverStatusFormatter';
import { formatNumber, formatPercent } from '../../utils/formatNumber';
import { NextActionsSection } from '../NextActionsSection';
import { PreviousActionsSection } from '../PreviousActionsSection';
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
        <InspectorRow label="Status" value={formatDriverStatus(state.status)} />
        <InspectorRow
          label="Rating"
          value={
            state.rating_count === 0
              ? '-'
              : `${formatNumber(state.current_rating, 2)} (${state.rating_count})`
          }
        />
        <InspectorRow label="Zone" value={state.zone_id || 'Unknown'} />
      </InspectorSection>

      {pending_offer && (
        <InspectorSection title="Pending Offer">
          <InspectorRow label="Trip ID" value={`${pending_offer.trip_id.slice(0, 8)}...`} />
          <InspectorRow
            label="Surge"
            value={`${formatNumber(pending_offer.surge_multiplier, 1)}x`}
          />
          <InspectorRow label="Rider Rating" value={formatNumber(pending_offer.rider_rating, 1)} />
          <InspectorRow label="ETA" value={`${pending_offer.eta_seconds}s`} />
        </InspectorSection>
      )}

      {active_trip && (
        <InspectorSection title="Active Trip">
          {active_trip.counterpart_name && (
            <InspectorRow
              label={
                active_trip.state === 'en_route_pickup'
                  ? 'En route to'
                  : active_trip.state === 'at_pickup'
                    ? 'Waiting for'
                    : active_trip.state === 'in_transit'
                      ? 'Driving'
                      : 'Rider'
              }
              value={active_trip.counterpart_name}
            />
          )}
          <InspectorRow label="State" value={formatTripState(active_trip.state)} />
          <InspectorRow label="Fare" value={`R$ ${formatNumber(active_trip.fare, 2)}`} />
          <InspectorRow label="Surge" value={`${formatNumber(active_trip.surge_multiplier, 1)}x`} />
        </InspectorSection>
      )}

      <InspectorSection title="Behavioral DNA">
        <InspectorRow label="Acceptance" value={formatPercent(dna.acceptance_rate, 0)} />
        <InspectorRow label="Service Quality" value={formatPercent(dna.service_quality, 0)} />
        <InspectorRow
          label="Avg Response Time"
          value={`${formatNumber(dna.avg_response_time, 1)}s`}
        />
        <InspectorRow label="Min Rider Rating" value={formatNumber(dna.min_rider_rating, 1)} />
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
            { value: `${formatNumber(statistics.acceptance_rate, 0)}%`, label: 'Accept Rate' },
          ]}
        />
        <InspectorRow label="Earnings" value={`R$ ${formatNumber(statistics.total_earnings, 2)}`} />
        {statistics.trips_completed > 0 && (
          <>
            <InspectorRow label="Avg Fare" value={`R$ ${formatNumber(statistics.avg_fare, 2)}`} />
            <InspectorRow
              label="Avg Pickup"
              value={`${formatNumber(statistics.avg_pickup_time_seconds, 0)}s`}
            />
            <InspectorRow
              label="Avg Trip"
              value={`${formatNumber(statistics.avg_trip_duration_minutes, 1)} min`}
            />
          </>
        )}
        {statistics.avg_rating_given > 0 && (
          <InspectorRow
            label="Avg Rating Given"
            value={formatNumber(statistics.avg_rating_given, 1)}
          />
        )}
      </InspectorSection>

      {state.is_puppet && (
        <InspectorSection title="Actions">
          <DriverActionsSection
            state={state}
            actionLoading={actionLoading}
            onAcceptOffer={onAcceptOffer || (() => {})}
            onRejectOffer={onRejectOffer || (() => {})}
            onStartTrip={onStartTrip || (() => {})}
            onCompleteTrip={onCompleteTrip || (() => {})}
            onCancelTrip={onCancelTrip || (() => {})}
            onToggleStatus={onToggleStatus || (() => {})}
          />
        </InspectorSection>
      )}

      {!state.is_puppet && (
        <PreviousActionsSection actionHistory={state.action_history} isPuppet={false} />
      )}
      {!state.is_puppet && <NextActionsSection nextAction={state.next_action} isPuppet={false} />}
    </>
  );
}
