import type { Rider, RiderState } from '../../types/api';
import { formatTripState } from '../../utils/tripStateFormatter';
import { NextActionsSection } from '../NextActionsSection';
import { InspectorSection } from './InspectorSection';
import { InspectorRow } from './InspectorRow';
import { StatsGrid } from './StatsGrid';
import { RiderActionsSection } from './RiderActionsSection';
import styles from './Inspector.module.css';

interface RiderInspectorProps {
  rider: Rider;
  state: RiderState | null;
  loading: boolean;
  error: string | null;
  actionLoading?: boolean;
  onRefetch: () => void;
  onRequestTrip?: () => void;
  onCancelTrip?: () => void;
}

export function RiderInspector({
  rider,
  state,
  loading,
  error,
  actionLoading = false,
  onRequestTrip,
  onCancelTrip,
}: RiderInspectorProps) {
  if (loading) {
    return <div className={styles.loading}>Loading...</div>;
  }

  if (error || !state) {
    const destinationText =
      rider.destination_latitude && rider.destination_longitude
        ? `${rider.destination_latitude.toFixed(4)}, ${rider.destination_longitude.toFixed(4)}`
        : 'Not set';

    return (
      <>
        <h3>Rider</h3>
        <InspectorRow label="ID" value={rider.id} isId />
        <InspectorRow label="Status" value={rider.status} />
        <InspectorRow label="Destination" value={destinationText} />
        {error && <div className={styles.error}>{error}</div>}
      </>
    );
  }

  const { dna, active_trip, statistics } = state;

  return (
    <>
      <div className={styles.header}>
        <h3>
          {dna.first_name} {dna.last_name}
        </h3>
      </div>
      {state.is_puppet && <span className={styles.badge}>Puppet Rider</span>}

      <InspectorSection title="Status">
        <InspectorRow label="ID" value={rider.id} isId />
        <InspectorRow label="Status" value={state.status} />
        <InspectorRow label="Rating" value={state.current_rating.toFixed(2)} />
        <InspectorRow label="Zone" value={state.zone_id || 'Unknown'} />
      </InspectorSection>

      {active_trip && (
        <InspectorSection title="Active Trip">
          {active_trip.counterpart_name && (
            <InspectorRow
              label="Driver"
              value={
                <>
                  <span>{active_trip.counterpart_name}</span>
                  {active_trip.state === 'matched' && ' assigned'}
                  {active_trip.state === 'driver_en_route' && ' is en route'}
                  {active_trip.state === 'driver_arrived' && ' has arrived'}
                  {active_trip.state === 'started' && ' (in trip)'}
                </>
              }
            />
          )}
          <InspectorRow label="State" value={formatTripState(active_trip.state)} />
          <InspectorRow label="Fare" value={`R$ ${active_trip.fare.toFixed(2)}`} />
          <InspectorRow label="Surge" value={`${active_trip.surge_multiplier.toFixed(1)}x`} />
        </InspectorSection>
      )}

      <InspectorSection title="Behavioral DNA">
        <InspectorRow
          label="Behavior Factor"
          value={`${(dna.behavior_factor * 100).toFixed(0)}%`}
        />
        <InspectorRow label="Patience" value={`${dna.patience_threshold}s`} />
        <InspectorRow label="Max Surge" value={`${dna.max_surge_multiplier.toFixed(1)}x`} />
        <InspectorRow label="Rides/Week" value={dna.avg_rides_per_week} />
      </InspectorSection>

      <InspectorSection title="Payment">
        <InspectorRow label="Method" value={dna.payment_method_type} />
        <InspectorRow label="Card" value={dna.payment_method_masked} />
      </InspectorSection>

      <InspectorSection title="Session Statistics">
        <StatsGrid
          stats={[
            { value: statistics.trips_completed, label: 'Completed' },
            { value: statistics.trips_cancelled, label: 'Cancelled' },
            { value: statistics.trips_requested, label: 'Requested' },
            { value: statistics.requests_timed_out, label: 'Timed Out' },
          ]}
        />
        <InspectorRow label="Total Spent" value={`R$ ${statistics.total_spent.toFixed(2)}`} />
        {statistics.trips_completed > 0 && (
          <>
            <InspectorRow label="Avg Fare" value={`R$ ${statistics.avg_fare.toFixed(2)}`} />
            <InspectorRow
              label="Avg Wait"
              value={`${statistics.avg_wait_time_seconds.toFixed(0)}s`}
            />
            <InspectorRow
              label="Avg Pickup Wait"
              value={`${statistics.avg_pickup_wait_seconds.toFixed(0)} sec`}
            />
            <InspectorRow
              label="Surge Trips"
              value={`${statistics.surge_trips_percentage.toFixed(0)}%`}
            />
          </>
        )}
        {statistics.avg_rating_given > 0 && (
          <InspectorRow label="Avg Rating Given" value={statistics.avg_rating_given.toFixed(1)} />
        )}
      </InspectorSection>

      {state.is_puppet && (
        <InspectorSection title="Actions">
          <RiderActionsSection
            state={state}
            actionLoading={actionLoading}
            onRequestTrip={onRequestTrip || (() => {})}
            onCancelTrip={onCancelTrip || (() => {})}
          />
        </InspectorSection>
      )}

      {!state.is_puppet && <NextActionsSection nextAction={state.next_action} isPuppet={false} />}
    </>
  );
}
