export interface SimulationStatus {
  state: 'stopped' | 'running' | 'draining' | 'paused';
  speed_multiplier: number;
  current_time: string;
  // Detailed driver metrics
  drivers_total: number;
  drivers_offline: number;
  drivers_available: number;
  drivers_en_route_pickup: number;
  drivers_on_trip: number;
  // Detailed rider metrics
  riders_total: number;
  riders_idle: number;
  riders_requesting: number;
  riders_awaiting_pickup: number;
  riders_on_trip: number;
  // Trips
  active_trips_count: number;
  uptime_seconds: number;
  real_time_ratio: number | null;
}

export type SpawnMode = 'immediate' | 'scheduled';

export interface Driver {
  id: string;
  latitude: number;
  longitude: number;
  status:
    | 'available'
    | 'offline'
    | 'en_route_pickup'
    | 'on_trip'
    | 'offer_pending'
    | 'driving_closer_to_home';
  rating: number;
  rating_count?: number;
  zone: string;
  heading?: number; // 0-360 degrees, 0 = North
}

// Trip state values for rider visualization
export type TripStateValue =
  | 'idle'
  | 'requested'
  | 'offer_sent'
  | 'offer_expired'
  | 'offer_rejected'
  | 'driver_assigned'
  | 'en_route_pickup'
  | 'at_pickup'
  | 'in_transit'
  | 'completed'
  | 'cancelled';

export interface Rider {
  id: string;
  latitude: number;
  longitude: number;
  status: 'idle' | 'requesting' | 'awaiting_pickup' | 'on_trip';
  trip_state?: TripStateValue;
  rating?: number;
  rating_count?: number;
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
  pickup_route: [number, number][]; // Driver → pickup route
  status: string;
  // Route progress indices for efficient updates (index into route geometry)
  route_progress_index?: number;
  pickup_route_progress_index?: number;
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
  type: 'driver_update' | 'rider_update' | 'trip_update' | 'surge_update';
  data: Driver | Rider | Trip | SurgeLevel;
}

export interface ZoneFeature {
  type: 'Feature';
  properties: {
    name: string;
    zone_id: string;
    subprefecture?: string;
    demand_multiplier?: number;
    surge_sensitivity?: number;
  };
  geometry: {
    type: 'Polygon';
    coordinates: number[][][];
  };
}

export interface ZoneData {
  feature: ZoneFeature;
  surge: number;
  driver_count: number;
}

export interface DemandPoint {
  latitude: number;
  longitude: number;
  weight: number;
}

export interface DriverMetrics {
  available: number;
  offline: number;
  en_route_pickup: number;
  on_trip: number;
  total: number;
}

export interface TripMetrics {
  active_trips: number;
  completed_today: number;
  cancelled_today: number;
  avg_fare: number;
  avg_duration_minutes: number;
  avg_match_seconds: number;
  avg_pickup_seconds: number;
  // Matching metrics
  offers_sent: number;
  offers_accepted: number;
  offers_rejected: number;
  offers_expired: number;
  matching_success_rate: number;
}

export interface RiderMetrics {
  idle: number;
  requesting: number;
  awaiting_pickup: number;
  in_transit: number;
  total: number;
}

export interface OverviewMetrics {
  total_drivers: number;
  online_drivers: number;
  total_riders: number;
  waiting_riders: number;
  in_transit_riders: number;
  active_trips: number;
  completed_trips_today: number;
}

// --- Agent State Inspection Types ---

export interface DriverDNA {
  acceptance_rate: number;
  cancellation_tendency: number;
  service_quality: number;
  avg_response_time: number;
  min_rider_rating: number;
  surge_acceptance_modifier: number;
  home_location: [number, number];
  shift_preference: string;
  avg_hours_per_day: number;
  avg_days_per_week: number;
  vehicle_make: string;
  vehicle_model: string;
  vehicle_year: number;
  license_plate: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
}

export interface RiderDNA {
  behavior_factor: number;
  patience_threshold: number;
  max_surge_multiplier: number;
  avg_rides_per_week: number;
  frequent_destinations: {
    coordinates: [number, number];
    weight: number;
    time_affinity?: number[];
  }[];
  home_location: [number, number];
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  payment_method_type: string;
  payment_method_masked: string;
}

// --- Agent Statistics Types ---

export interface DriverStatistics {
  // Trip statistics
  trips_completed: number;
  trips_cancelled: number;
  cancellation_rate: number;
  // Offer statistics
  offers_received: number;
  offers_accepted: number;
  offers_rejected: number;
  offers_expired: number;
  acceptance_rate: number;
  // Earnings (BRL)
  total_earnings: number;
  avg_fare: number;
  // Performance metrics
  avg_pickup_time_seconds: number;
  avg_trip_duration_minutes: number;
  avg_rating_given: number;
}

export interface RiderStatistics {
  // Trip statistics
  trips_completed: number;
  trips_cancelled: number;
  trips_requested: number;
  cancellation_rate: number;
  requests_timed_out: number;
  // Spending (BRL)
  total_spent: number;
  avg_fare: number;
  // Wait time metrics
  avg_wait_time_seconds: number;
  avg_pickup_wait_seconds: number;
  // Behavior metrics
  avg_rating_given: number;
  surge_trips_percentage: number;
}

export interface ActiveTripInfo {
  trip_id: string;
  state: TripStateValue;
  rider_id: string | null;
  driver_id: string | null;
  counterpart_name: string | null; // Rider name (for driver) or driver name (for rider)
  pickup_location: [number, number];
  dropoff_location: [number, number];
  surge_multiplier: number;
  fare: number;
}

export interface PendingOfferInfo {
  trip_id: string;
  surge_multiplier: number;
  rider_rating: number;
  eta_seconds: number;
}

export type NextActionType =
  | 'go_online'
  | 'go_offline'
  | 'accept_reject_offer'
  | 'request_ride'
  | 'patience_timeout';

export interface NextAction {
  action_type: NextActionType;
  scheduled_at: number;
  scheduled_at_iso: string;
  description: string;
}

export interface DriverState {
  driver_id: string;
  status: Driver['status'];
  location: [number, number] | null;
  current_rating: number;
  rating_count: number;
  active_trip: ActiveTripInfo | null;
  pending_offer: PendingOfferInfo | null;
  next_action: NextAction | null;
  zone_id: string | null;
  dna: DriverDNA;
  statistics: DriverStatistics;
  is_ephemeral: boolean;
  is_puppet: boolean;
}

export interface RiderState {
  rider_id: string;
  status: Rider['status'];
  location: [number, number] | null;
  current_rating: number;
  rating_count: number;
  active_trip: ActiveTripInfo | null;
  next_action: NextAction | null;
  zone_id: string | null;
  dna: RiderDNA;
  statistics: RiderStatistics;
  is_ephemeral: boolean;
  is_puppet: boolean;
}

// --- Service Health Types ---

export type ServiceStatus = 'healthy' | 'degraded' | 'unhealthy';

export interface ServiceHealth {
  status: ServiceStatus;
  latency_ms: number | null;
  message: string | null;
}

export interface StreamProcessorHealth {
  status: ServiceStatus;
  latency_ms: number | null;
  message: string | null;
  kafka_connected: boolean | null;
  redis_connected: boolean | null;
}

export interface DetailedHealthResponse {
  overall_status: ServiceStatus;
  redis: ServiceHealth;
  osrm: ServiceHealth;
  kafka: ServiceHealth;
  simulation_engine: ServiceHealth;
  stream_processor: StreamProcessorHealth;
  timestamp: string;
}

// --- Performance Metrics Types ---

export interface LatencyMetrics {
  avg_ms: number;
  p95_ms: number;
  p99_ms: number;
  count: number;
}

export interface EventsMetrics {
  gps_pings_per_sec: number;
  trip_events_per_sec: number;
  driver_status_per_sec: number;
  total_per_sec: number;
}

export interface LatencySummary {
  osrm: LatencyMetrics | null;
  kafka: LatencyMetrics | null;
  redis: LatencyMetrics | null;
}

export interface ErrorStats {
  count: number;
  per_second: number;
  by_type: Record<string, number>;
}

export interface ErrorSummary {
  osrm: ErrorStats | null;
  kafka: ErrorStats | null;
  redis: ErrorStats | null;
}

export interface QueueDepths {
  pending_offers: number;
  simpy_events: number;
}

export interface ResourceMetrics {
  memory_rss_mb: number;
  memory_percent: number;
  cpu_percent: number;
  thread_count: number;
}

export interface MemoryMetrics {
  rss_mb: number;
  percent: number;
}

export interface StreamProcessorLatency {
  avg_ms: number;
  p95_ms: number;
  count: number;
}

export interface StreamProcessorMetrics {
  messages_consumed_per_sec: number;
  messages_published_per_sec: number;
  gps_aggregation_ratio: number;
  redis_publish_latency: StreamProcessorLatency;
  publish_errors_per_sec: number;
  kafka_connected: boolean;
  redis_connected: boolean;
  uptime_seconds: number;
}

export interface PerformanceMetrics {
  events: EventsMetrics;
  latency: LatencySummary;
  errors: ErrorSummary;
  queue_depths: QueueDepths;
  memory: MemoryMetrics;
  resources: ResourceMetrics | null;
  stream_processor: StreamProcessorMetrics | null;
  timestamp: number;
}

// Frontend-only metrics
export interface FrontendMetrics {
  ws_messages_per_sec: number;
  render_fps: number;
}

// --- Infrastructure Metrics Types ---

export type ContainerStatus = 'healthy' | 'degraded' | 'unhealthy' | 'stopped';

export interface ServiceMetrics {
  name: string;
  status: ContainerStatus;
  latency_ms: number | null;
  message: string | null;
  memory_used_mb: number;
  memory_limit_mb: number;
  memory_percent: number;
  cpu_percent: number;
}

export interface InfrastructureResponse {
  services: ServiceMetrics[];
  overall_status: ContainerStatus;
  cadvisor_available: boolean;
  timestamp: number;
  // System-wide totals (normalized by total cores)
  total_cpu_percent: number;
  total_memory_used_mb: number;
  total_memory_capacity_mb: number;
  total_memory_percent: number;
  total_cores: number;
  discovery_error?: string;
}
