import type { Rider } from '../types/api';

const RIDER_STATUS_LABELS: Record<Rider['status'], string> = {
  idle: 'Idle',
  requesting: 'Requesting',
  awaiting_pickup: 'Awaiting Pickup',
  on_trip: 'On Trip',
};

export function formatRiderStatus(status: Rider['status']): string {
  return RIDER_STATUS_LABELS[status];
}
