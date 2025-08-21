export interface SimulationStatus {
  state: 'STOPPED' | 'RUNNING' | 'DRAINING' | 'PAUSED';
  speed_multiplier: number;
  current_time: string;
  drivers_count: number;
  riders_count: number;
  active_trips_count: number;
  uptime_seconds: number;
}

export interface Driver {
  id: string;
  latitude: number;
  longitude: number;
  status: 'online' | 'offline' | 'busy' | 'en_route';
  rating: number;
  zone: string;
}

export interface Rider {
  id: string;
  latitude: number;
  longitude: number;
  status: 'waiting' | 'in_transit';
  destination_latitude?: number;
  destination_longitude?: number;
}

export interface Trip {
  id: string;
  driver_id: string;
  rider_id: string;
  pickup_latitude: number;
  pickup_longitude: number;
  dropoff_latitude: number;
  dropoff_longitude: number;
  route: [number, number][];
  status: string;
}

export interface SurgeLevel {
  zone: string;
  multiplier: number;
}

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

export interface IncrementalUpdate {
  type: 'driver_update' | 'rider_update' | 'trip_update' | 'surge_update' | 'gps_ping';
  data: Driver | Rider | Trip | SurgeLevel | GPSTrail;
}

export interface GPSTrail {
  id: string;
  path: [number, number, number][];
}
