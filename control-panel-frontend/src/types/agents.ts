export type DriverStatus = 'online' | 'offline' | 'busy' | 'en_route';
export type RiderStatus = 'waiting' | 'in_transit';
export type TripStatus =
  | 'REQUESTED'
  | 'OFFER_SENT'
  | 'MATCHED'
  | 'DRIVER_EN_ROUTE'
  | 'DRIVER_ARRIVED'
  | 'STARTED'
  | 'COMPLETED'
  | 'CANCELLED';

export interface DriverDNA {
  acceptance_rate: number;
  avg_speed_factor: number;
  service_quality: number;
  work_hours_per_day: number;
}

export interface RiderDNA {
  trip_frequency: number;
  patience_seconds: number;
  preferred_rating_threshold: number;
}
