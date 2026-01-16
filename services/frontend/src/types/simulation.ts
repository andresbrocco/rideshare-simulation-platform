export interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch?: number;
  bearing?: number;
}

export interface SimulationConfig {
  speed_multiplier: number;
  driver_count: number;
  rider_spawn_rate: number;
}

export interface MetricsData {
  timestamp: string;
  total_trips: number;
  completed_trips: number;
  cancelled_trips: number;
  active_drivers: number;
  online_drivers: number;
  avg_wait_time: number;
  avg_trip_duration: number;
  revenue: number;
}
