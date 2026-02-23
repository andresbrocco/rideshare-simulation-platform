import type { Driver } from '../types/api';

const DRIVER_STATUS_LABELS: Record<Driver['status'], string> = {
  available: 'Available',
  offline: 'Offline',
  en_route_pickup: 'To Pickup',
  on_trip: 'On Trip',
  offer_pending: 'Offer Pending',
};

export function formatDriverStatus(status: Driver['status']): string {
  return DRIVER_STATUS_LABELS[status] ?? status;
}
