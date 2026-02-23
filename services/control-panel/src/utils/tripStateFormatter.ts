import type { TripStateValue } from '../types/api';

const STATE_LABELS: Record<TripStateValue, string> = {
  idle: 'Idle',
  requested: 'Requesting ride',
  offer_sent: 'Finding driver',
  offer_expired: 'Finding another driver',
  offer_rejected: 'Finding another driver',
  driver_assigned: 'Driver assigned',
  en_route_pickup: 'Waiting for pickup',
  at_pickup: 'Driver at pickup',
  in_transit: 'In transit',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

export function formatTripState(state: TripStateValue): string {
  return STATE_LABELS[state] ?? state;
}
