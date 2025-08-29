import type { Driver, Rider, Trip, SimulationStatus } from './api';

export interface StateSnapshot {
  type: 'snapshot';
  data: {
    drivers: Driver[];
    riders: Rider[];
    trips: Trip[];
    surge: Record<string, number>;
    simulation: SimulationStatus;
  };
}

export interface DriverUpdate {
  type: 'driver_update';
  data: Driver;
}

export interface RiderUpdate {
  type: 'rider_update';
  data: Rider;
}

export interface TripUpdate {
  type: 'trip_update';
  data: Trip;
}

export interface SurgeUpdate {
  type: 'surge_update';
  data: { zone: string; multiplier: number };
}

export interface GPSPing {
  type: 'gps_ping';
  data: {
    entity_id: string;
    entity_type: 'driver' | 'rider';
    latitude: number;
    longitude: number;
    timestamp: number;
  };
}

export interface SimulationStatusUpdate {
  type: 'simulation_status';
  data: SimulationStatus;
}

export type WebSocketMessage =
  | StateSnapshot
  | DriverUpdate
  | RiderUpdate
  | TripUpdate
  | SurgeUpdate
  | GPSPing
  | SimulationStatusUpdate;
