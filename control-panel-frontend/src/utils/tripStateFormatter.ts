const stateLabels: Record<string, string> = {
  requested: 'Waiting for match',
  offer_sent: 'Offer sent to driver',
  offer_expired: 'Offer expired',
  offer_rejected: 'Offer rejected',
  matched: 'Driver assigned',
  driver_en_route: 'Driver en route',
  driver_arrived: 'Driver arrived',
  started: 'In progress',
  completed: 'Completed',
  cancelled: 'Cancelled',
};

export function formatTripState(state: string): string {
  return stateLabels[state] || state;
}
