export interface DriverDNAOverride {
  acceptance_rate: number;
  cancellation_tendency: number;
  service_quality: number;
  response_time: number;
  min_rider_rating: number;
  surge_acceptance_modifier: number;
}

export interface RiderDNAOverride {
  behavior_factor: number;
  patience_threshold: number;
  max_surge_multiplier: number;
  avg_rides_per_week: number;
}

export interface DriverPreset {
  id: string;
  name: string;
  description: string;
  dna: DriverDNAOverride;
}

export interface RiderPreset {
  id: string;
  name: string;
  description: string;
  dna: RiderDNAOverride;
}

export const DRIVER_PRESETS: DriverPreset[] = [
  {
    id: 'reliable',
    name: 'Reliable Driver',
    description: 'High acceptance, excellent service',
    dna: {
      acceptance_rate: 0.95,
      cancellation_tendency: 0.05,
      service_quality: 0.9,
      response_time: 4.0,
      min_rider_rating: 3.0,
      surge_acceptance_modifier: 1.2,
    },
  },
  {
    id: 'picky',
    name: 'Picky Driver',
    description: 'Selective, prefers high-rated riders',
    dna: {
      acceptance_rate: 0.6,
      cancellation_tendency: 0.2,
      service_quality: 0.85,
      response_time: 8.0,
      min_rider_rating: 4.5,
      surge_acceptance_modifier: 1.8,
    },
  },
  {
    id: 'average',
    name: 'Average Driver',
    description: 'Typical driver behavior',
    dna: {
      acceptance_rate: 0.8,
      cancellation_tendency: 0.1,
      service_quality: 0.75,
      response_time: 6.0,
      min_rider_rating: 3.5,
      surge_acceptance_modifier: 1.4,
    },
  },
];

export const RIDER_PRESETS: RiderPreset[] = [
  {
    id: 'patient',
    name: 'Patient Rider',
    description: 'Waits longer, tolerates higher surge',
    dna: {
      behavior_factor: 0.9,
      patience_threshold: 280,
      max_surge_multiplier: 2.5,
      avg_rides_per_week: 8,
    },
  },
  {
    id: 'impatient',
    name: 'Impatient Rider',
    description: 'Short patience, low surge tolerance',
    dna: {
      behavior_factor: 0.4,
      patience_threshold: 130,
      max_surge_multiplier: 1.3,
      avg_rides_per_week: 3,
    },
  },
  {
    id: 'regular',
    name: 'Regular Rider',
    description: 'Typical rider behavior',
    dna: {
      behavior_factor: 0.7,
      patience_threshold: 200,
      max_surge_multiplier: 1.8,
      avg_rides_per_week: 5,
    },
  },
];

// Simple placement mode for puppet agents
export type PlacementMode = {
  type: 'driver' | 'rider';
};
