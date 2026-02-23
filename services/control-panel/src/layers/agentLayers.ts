import { IconLayer, PathLayer, LineLayer } from '@deck.gl/layers';
import type { Driver, Rider, Trip, TripStateValue } from '../types/api';
import { STAGE_RGB, STAGE_TRAIL } from '../theme';
import type { RgbTuple } from '../utils/colorUtils';

// Monochrome white icons — deck.gl getColor tinting provides phase-based colors
const CAR_ICON = '/icons/car.png';
const PERSON_ICON = '/icons/person.png';

// Checkered flag icon for trip destinations
const FLAG_ICON = '/icons/flag-checkered.png';
const FLAG_ICON_MAPPING = {
  flag: { x: 0, y: 0, width: 100, height: 100, anchorY: 100, anchorX: 0 },
};

// Home marker icon for inspector home location
const HOME_ICON = '/icons/home.png';
const HOME_ICON_MAPPING = {
  home: { x: 0, y: 0, width: 100, height: 100, anchorY: 100, anchorX: 50, mask: true },
};

// Icon mapping for deck.gl (defines icon bounds within the image)
const CAR_ICON_MAPPING = {
  car: { x: 0, y: 0, width: 100, height: 100, anchorY: 50, anchorX: 50, mask: true },
};
const PERSON_ICON_MAPPING = {
  person: { x: 0, y: 0, width: 100, height: 100, anchorY: 50, anchorX: 50, mask: true },
};

// Driver status colors by trip lifecycle phase
export const DRIVER_COLORS: Record<Driver['status'], RgbTuple> = {
  available: STAGE_RGB.available.base,
  offline: STAGE_RGB.idle.base,
  en_route_pickup: STAGE_RGB.pickup.base,
  on_trip: STAGE_RGB.transit.base,
  offer_pending: STAGE_RGB.available.base,
  driving_closer_to_home: STAGE_RGB.repositioning.base,
};

// Rider colors by trip lifecycle phase
export const RIDER_TRIP_STATE_COLORS: Record<TripStateValue | 'default', RgbTuple> = {
  idle: STAGE_RGB.idle.light,
  requested: STAGE_RGB.requesting.base,
  offer_sent: STAGE_RGB.requesting.base,
  offer_expired: STAGE_RGB.cancelled.base,
  offer_rejected: STAGE_RGB.cancelled.base,
  driver_assigned: STAGE_RGB.pickup.base,
  en_route_pickup: STAGE_RGB.pickup.light,
  at_pickup: STAGE_RGB.pickup.lighter,
  in_transit: STAGE_RGB.transit.base,
  completed: STAGE_RGB.completed.base,
  cancelled: STAGE_RGB.cancelled.base,
  default: STAGE_RGB.idle.light,
};

// Helper to get rider color from trip state
export function getRiderColor(rider: Rider): RgbTuple {
  const tripState = rider.trip_state || 'idle';
  return RIDER_TRIP_STATE_COLORS[tripState] || RIDER_TRIP_STATE_COLORS.default;
}

// ============================================================================
// Route Split Cache - Avoids redundant route calculations
// ============================================================================

interface CachedRouteSplit {
  completed: [number, number][];
  remaining: [number, number][];
  swappedCompleted: [number, number][];
  swappedRemaining: [number, number][];
}

const routeSplitCache = new Map<string, CachedRouteSplit>();
const MAX_CACHE_SIZE = 1000;

function getCacheKey(
  tripId: string,
  progressIndex: number | undefined,
  routeType: 'pickup' | 'trip'
): string {
  return `${tripId}:${routeType}:${progressIndex ?? 0}`;
}

// Helper to swap coordinates from [lat, lon] to [lon, lat] for deck.gl
function swapCoordinatesInternal(route: [number, number][]): [number, number][] {
  return route.map(([lat, lon]) => [lon, lat]);
}

// Helper to split route into completed and remaining portions
function splitRouteInternal(
  route: [number, number][],
  progressIndex: number | undefined
): { completed: [number, number][]; remaining: [number, number][] } {
  if (!route || route.length === 0 || progressIndex === undefined || progressIndex === 0) {
    return { completed: [], remaining: route || [] };
  }
  const safeIndex = Math.min(progressIndex, route.length - 1);
  return {
    // Include current point in both for visual continuity
    completed: route.slice(0, safeIndex + 1),
    remaining: route.slice(safeIndex),
  };
}

/**
 * Get cached route split with swapped coordinates.
 * Caches both the split result and coordinate transformation to avoid redundant calculations.
 */
function getCachedRouteSplit(
  tripId: string,
  route: [number, number][],
  progressIndex: number | undefined,
  routeType: 'pickup' | 'trip'
): CachedRouteSplit {
  const key = getCacheKey(tripId, progressIndex, routeType);

  const cached = routeSplitCache.get(key);
  if (cached) {
    return cached;
  }

  // LRU-style cleanup when cache is full
  if (routeSplitCache.size >= MAX_CACHE_SIZE) {
    // Delete oldest entries (first 20%)
    const keysToDelete = Array.from(routeSplitCache.keys()).slice(
      0,
      Math.floor(MAX_CACHE_SIZE / 5)
    );
    keysToDelete.forEach((k) => routeSplitCache.delete(k));
  }

  const { completed, remaining } = splitRouteInternal(route, progressIndex);
  const result: CachedRouteSplit = {
    completed,
    remaining,
    swappedCompleted: swapCoordinatesInternal(completed),
    swappedRemaining: swapCoordinatesInternal(remaining),
  };

  routeSplitCache.set(key, result);
  return result;
}

/**
 * Clear the route cache. Call this on simulation reset to free memory.
 */
export function clearRouteCache(): void {
  routeSplitCache.clear();
}

/**
 * Evict all cache entries for a specific trip. Call this when a trip completes or is cancelled
 * to prevent stale route data from accumulating.
 */
export function evictTripFromRouteCache(tripId: string): void {
  for (const key of routeSplitCache.keys()) {
    if (key.startsWith(tripId + ':')) {
      routeSplitCache.delete(key);
    }
  }
}

// ============================================================================
// Driver Layers
// ============================================================================

export function createOnlineDriversLayer(drivers: Driver[], scaleFactor: number = 1) {
  const onlineDrivers = drivers.filter((d) => d.status === 'available');
  return new IconLayer({
    id: 'online-drivers',
    data: onlineDrivers,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: CAR_ICON,
    iconMapping: CAR_ICON_MAPPING,
    getIcon: () => 'car',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 30 * scaleFactor,

    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getAngle: (d: Driver) => 90 - (d.heading ?? 0), // Rotate icon to face direction of travel
    getColor: STAGE_RGB.available.base,
  });
}

export function createRepositioningDriversLayer(drivers: Driver[], scaleFactor: number = 1) {
  const repositioningDrivers = drivers.filter((d) => d.status === 'driving_closer_to_home');
  return new IconLayer({
    id: 'repositioning-drivers',
    data: repositioningDrivers,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: CAR_ICON,
    iconMapping: CAR_ICON_MAPPING,
    getIcon: () => 'car',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 30 * scaleFactor,

    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getAngle: (d: Driver) => 90 - (d.heading ?? 0),
    getColor: STAGE_RGB.repositioning.base,
  });
}

export function createOfflineDriversLayer(drivers: Driver[], scaleFactor: number = 1) {
  const offlineDrivers = drivers.filter((d) => d.status === 'offline');
  return new IconLayer({
    id: 'offline-drivers',
    data: offlineDrivers,
    pickable: true,

    iconAtlas: CAR_ICON,
    iconMapping: CAR_ICON_MAPPING,
    getIcon: () => 'car',

    sizeMinPixels: 16,
    sizeMaxPixels: 32,
    getSize: 24 * scaleFactor,

    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getAngle: (d: Driver) => 90 - (d.heading ?? 0),
    getColor: [...STAGE_RGB.idle.base, 200],
  });
}

export function createEnRoutePickupDriversLayer(drivers: Driver[], scaleFactor: number = 1) {
  const enRoutePickupDrivers = drivers.filter((d) => d.status === 'en_route_pickup');
  return new IconLayer({
    id: 'en-route-pickup-drivers',
    data: enRoutePickupDrivers,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: CAR_ICON,
    iconMapping: CAR_ICON_MAPPING,
    getIcon: () => 'car',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 30 * scaleFactor,

    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getAngle: (d: Driver) => 90 - (d.heading ?? 0),
    getColor: STAGE_RGB.pickup.base,
  });
}

export function createWithPassengerDriversLayer(drivers: Driver[], scaleFactor: number = 1) {
  const withPassengerDrivers = drivers.filter((d) => d.status === 'on_trip');
  return new IconLayer({
    id: 'with-passenger-drivers',
    data: withPassengerDrivers,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: CAR_ICON,
    iconMapping: CAR_ICON_MAPPING,
    getIcon: () => 'car',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 30 * scaleFactor,

    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getAngle: (d: Driver) => 90 - (d.heading ?? 0),
    getColor: STAGE_RGB.transit.base,
  });
}

// Trip states that have their own dedicated rider layers
const ACTIVE_TRIP_STATES = new Set<string>([
  'requested',
  'offer_sent',
  'driver_assigned',
  'en_route_pickup',
  'at_pickup',
  'in_transit',
]);

export function createOfflineRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  // Catch-all: render riders without a trip_state OR with any state not claimed by another layer
  const offlineRiders = riders.filter(
    (r) => !r.trip_state || !ACTIVE_TRIP_STATES.has(r.trip_state)
  );
  return new IconLayer({
    id: 'offline-riders',
    data: offlineRiders,
    pickable: true,

    iconAtlas: PERSON_ICON,
    iconMapping: PERSON_ICON_MAPPING,
    getIcon: () => 'person',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 30 * scaleFactor,

    getPosition: (d: Rider) => [d.longitude, d.latitude],
    getColor: STAGE_RGB.idle.light,
  });
}

export function createRequestingRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  // Riders in REQUESTED, OFFER_SENT, or MATCHED states (pre-pickup phase)
  const requestingRiders = riders.filter(
    (r) =>
      r.trip_state === 'requested' ||
      r.trip_state === 'offer_sent' ||
      r.trip_state === 'driver_assigned'
  );
  return new IconLayer({
    id: 'requesting-riders',
    data: requestingRiders,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: PERSON_ICON,
    iconMapping: PERSON_ICON_MAPPING,
    getIcon: () => 'person',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 28 * scaleFactor,

    getPosition: (d: Rider) => [d.longitude, d.latitude],
    getColor: STAGE_RGB.requesting.base,
  });
}

export function createEnRouteRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  // Riders in DRIVER_EN_ROUTE state (driver on the way)
  const enRouteRiders = riders.filter((r) => r.trip_state === 'en_route_pickup');
  return new IconLayer({
    id: 'en-route-riders',
    data: enRouteRiders,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: PERSON_ICON,
    iconMapping: PERSON_ICON_MAPPING,
    getIcon: () => 'person',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 28 * scaleFactor,

    getPosition: (d: Rider) => [d.longitude, d.latitude],
    getColor: STAGE_RGB.pickup.light,
  });
}

export function createArrivedRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  // Riders in DRIVER_ARRIVED state (driver at pickup location)
  const arrivedRiders = riders.filter((r) => r.trip_state === 'at_pickup');
  return new IconLayer({
    id: 'arrived-riders',
    data: arrivedRiders,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: PERSON_ICON,
    iconMapping: PERSON_ICON_MAPPING,
    getIcon: () => 'person',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 28 * scaleFactor,

    getPosition: (d: Rider) => [d.longitude, d.latitude],
    getColor: STAGE_RGB.pickup.lighter,
  });
}

export function createInTransitRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  // Riders in STARTED state (in vehicle)
  const inTransitRiders = riders.filter((r) => r.trip_state === 'in_transit');
  return new IconLayer({
    id: 'in-transit-riders',
    data: inTransitRiders,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: PERSON_ICON,
    iconMapping: PERSON_ICON_MAPPING,
    getIcon: () => 'person',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 28 * scaleFactor,

    getPosition: (d: Rider) => [d.longitude, d.latitude],
    getColor: STAGE_RGB.transit.base,
  });
}

// Helper to swap coordinates from [lat, lon] to [lon, lat] for deck.gl
function swapCoordinates(route: [number, number][]): [number, number][] {
  return route.map(([lat, lon]) => [lon, lat]);
}

// Pending routes: Light orange solid - requesting phase
export function createPendingRouteLayer(
  trips: Trip[],
  visible: boolean = true,
  scaleFactor: number = 1
) {
  const pendingTrips = trips.filter(
    (t) =>
      t.route &&
      t.route.length > 0 &&
      (t.status === 'requested' || t.status === 'offer_sent' || t.status === 'driver_assigned')
  );

  return new PathLayer({
    id: 'pending-routes',
    data: pendingTrips,
    visible,
    pickable: true,
    getPath: (d: Trip) => swapCoordinates(d.route),
    getColor: STAGE_RGB.requesting.route,
    widthUnits: 'pixels',
    getWidth: 4 * scaleFactor,
  });
}

// Pickup routes: Gold dashed - pickup phase
export function createPickupRouteLayer(trips: Trip[], visible: boolean = true) {
  const tripsWithPickupRoutes = trips.filter(
    (t) =>
      t.pickup_route &&
      t.pickup_route.length > 0 &&
      (t.status === 'en_route_pickup' || t.status === 'at_pickup')
  );

  return new PathLayer({
    id: 'pickup-routes',
    data: tripsWithPickupRoutes,
    visible,
    pickable: true,
    getPath: (d: Trip) => swapCoordinates(d.pickup_route),
    getColor: STAGE_RGB.pickup.route,
    widthUnits: 'pixels',
    getWidth: 4,
    getDashArray: [8, 4], // Dashed pattern
  });
}

// Trip routes: Light blue solid - in transit phase
export function createPathLayer(trips: Trip[], visible: boolean = true) {
  const activeTrips = trips.filter(
    (t) => t.route && t.route.length > 0 && t.status === 'in_transit'
  );

  return new PathLayer({
    id: 'trip-routes',
    data: activeTrips,
    visible,
    pickable: true,
    getPath: (d: Trip) => swapCoordinates(d.route),
    getColor: STAGE_RGB.transit.route,
    widthUnits: 'pixels',
    getWidth: 5,
  });
}

// Completed pickup route trail: Faded gold - portion already traveled
export function createCompletedPickupRouteLayer(
  trips: Trip[],
  visible: boolean = true,
  scaleFactor: number = 1
) {
  const tripsWithProgress = trips.filter(
    (t) =>
      t.pickup_route &&
      t.pickup_route.length > 0 &&
      t.status === 'en_route_pickup' &&
      t.pickup_route_progress_index !== undefined &&
      t.pickup_route_progress_index > 0
  );

  // Pre-compute split routes for each trip using cache
  const trailData = tripsWithProgress
    .map((t) => {
      const cached = getCachedRouteSplit(
        t.id,
        t.pickup_route,
        t.pickup_route_progress_index,
        'pickup'
      );
      return {
        trip: t,
        path: cached.swappedCompleted,
      };
    })
    .filter((d) => d.path.length > 1);

  return new PathLayer({
    id: 'completed-pickup-routes',
    data: trailData,
    visible,
    pickable: false,
    getPath: (d: { path: [number, number][] }) => d.path,
    getColor: [...STAGE_TRAIL.pickup],
    widthUnits: 'pixels',
    getWidth: 4 * scaleFactor,
  });
}

// Remaining pickup route: Solid gold dashed - portion still to travel
export function createRemainingPickupRouteLayer(
  trips: Trip[],
  visible: boolean = true,
  scaleFactor: number = 1
) {
  // Only show during en_route_pickup - once arrived, pickup route is complete
  const tripsWithPickupRoutes = trips.filter(
    (t) => t.pickup_route && t.pickup_route.length > 0 && t.status === 'en_route_pickup'
  );

  // Pre-compute remaining routes for each trip using cache
  const remainingData = tripsWithPickupRoutes
    .map((t) => {
      const cached = getCachedRouteSplit(
        t.id,
        t.pickup_route,
        t.pickup_route_progress_index,
        'pickup'
      );
      return {
        trip: t,
        path: cached.swappedRemaining,
      };
    })
    .filter((d) => d.path.length > 1);

  return new PathLayer({
    id: 'remaining-pickup-routes',
    data: remainingData,
    visible,
    pickable: true,
    getPath: (d: { path: [number, number][] }) => d.path,
    getColor: STAGE_RGB.pickup.route,
    widthUnits: 'pixels',
    getWidth: 4 * scaleFactor,
    getDashArray: [8, 4], // Dashed pattern
  });
}

// Completed trip route trail: Faded light blue - portion already traveled
export function createCompletedTripRouteLayer(
  trips: Trip[],
  visible: boolean = true,
  scaleFactor: number = 1
) {
  const tripsWithProgress = trips.filter(
    (t) =>
      t.route &&
      t.route.length > 0 &&
      t.status === 'in_transit' &&
      t.route_progress_index !== undefined &&
      t.route_progress_index > 0
  );

  // Pre-compute split routes for each trip using cache
  const trailData = tripsWithProgress
    .map((t) => {
      const cached = getCachedRouteSplit(t.id, t.route, t.route_progress_index, 'trip');
      return {
        trip: t,
        path: cached.swappedCompleted,
      };
    })
    .filter((d) => d.path.length > 1);

  return new PathLayer({
    id: 'completed-trip-routes',
    data: trailData,
    visible,
    pickable: false,
    getPath: (d: { path: [number, number][] }) => d.path,
    getColor: [...STAGE_TRAIL.transit],
    widthUnits: 'pixels',
    getWidth: 5 * scaleFactor,
  });
}

// Remaining trip route: Solid light blue - portion still to travel
export function createRemainingTripRouteLayer(
  trips: Trip[],
  visible: boolean = true,
  scaleFactor: number = 1
) {
  const activeTrips = trips.filter(
    (t) => t.route && t.route.length > 0 && t.status === 'in_transit'
  );

  // Pre-compute remaining routes for each trip using cache
  const remainingData = activeTrips
    .map((t) => {
      const cached = getCachedRouteSplit(t.id, t.route, t.route_progress_index, 'trip');
      return {
        trip: t,
        path: cached.swappedRemaining,
      };
    })
    .filter((d) => d.path.length > 1);

  return new PathLayer({
    id: 'remaining-trip-routes',
    data: remainingData,
    visible,
    pickable: true,
    getPath: (d: { path: [number, number][] }) => d.path,
    getColor: STAGE_RGB.transit.route,
    widthUnits: 'pixels',
    getWidth: 5 * scaleFactor,
  });
}

// Destination flags: Flag icon at dropoff location for active trips
export function createDestinationFlagLayer(
  trips: Trip[],
  visible: boolean = true,
  scaleFactor: number = 1
) {
  const activeTrips = trips.filter(
    (t) => t.route && t.route.length > 0 && t.status === 'in_transit'
  );

  return new IconLayer({
    id: 'destination-flags',
    data: activeTrips,
    visible,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: FLAG_ICON,
    iconMapping: FLAG_ICON_MAPPING,
    getIcon: () => 'flag',

    sizeMinPixels: 19,
    sizeMaxPixels: 38,
    getSize: 29 * scaleFactor,

    getPosition: (d: Trip) => [d.dropoff_longitude, d.dropoff_latitude],
  });
}

// All driver statuses use the same monochrome icon, tinted via getColor
function getDriverIconUrl(): string {
  return CAR_ICON;
}

export function createDriverLayer(drivers: Driver[], scaleFactor: number = 1) {
  // Group drivers by status for separate layers (since iconAtlas can't change per-item)
  const layers = [];
  const statusGroups = {
    available: drivers.filter((d) => d.status === 'available'),
    offline: drivers.filter((d) => d.status === 'offline'),
    en_route_pickup: drivers.filter((d) => d.status === 'en_route_pickup'),
    on_trip: drivers.filter((d) => d.status === 'on_trip'),
    offer_pending: drivers.filter((d) => d.status === 'offer_pending'),
    driving_closer_to_home: drivers.filter((d) => d.status === 'driving_closer_to_home'),
  };

  for (const [status, group] of Object.entries(statusGroups)) {
    if (group.length > 0) {
      layers.push(
        new IconLayer({
          id: `drivers-${status}`,
          data: group,
          pickable: true,

          iconAtlas: getDriverIconUrl(),
          iconMapping: CAR_ICON_MAPPING,
          getIcon: () => 'car',

          sizeMinPixels: 12,
          sizeMaxPixels: 30,
          getSize: 24 * scaleFactor,

          getPosition: (d: Driver) => [d.longitude, d.latitude],
          getAngle: (d: Driver) => 90 - (d.heading ?? 0),
          getColor: DRIVER_COLORS[status as Driver['status']] || DRIVER_COLORS.available,
        })
      );
    }
  }

  return layers;
}

interface MatchingPair {
  riderPos: [number, number]; // [lon, lat] — deck.gl order
  driverPos: [number, number];
}

export function createMatchingLineLayer(
  trips: Trip[],
  drivers: Driver[],
  riders: Rider[],
  blinkOn: boolean
): LineLayer<MatchingPair> {
  const pairs: MatchingPair[] = [];

  for (const trip of trips) {
    if (trip.status !== 'offer_sent') continue;
    const driver = drivers.find((d) => d.id === trip.driver_id);
    const rider = riders.find((r) => r.id === trip.rider_id);
    if (!driver || !rider) continue;
    pairs.push({
      driverPos: [driver.longitude, driver.latitude],
      riderPos: [rider.longitude, rider.latitude],
    });
  }

  const alpha = blinkOn ? 220 : 0;

  return new LineLayer<MatchingPair>({
    id: 'matching-lines',
    data: pairs,
    pickable: false,
    getSourcePosition: (d) => d.driverPos,
    getTargetPosition: (d) => d.riderPos,
    getColor: [255, 255, 255, alpha],
    getWidth: 2,
    widthUnits: 'pixels',
  });
}

// All rider states use the same monochrome icon, tinted via getColor
function getRiderIconUrl(): string {
  return PERSON_ICON;
}

export function createRiderLayer(riders: Rider[], scaleFactor: number = 1) {
  // Group riders by trip_state for separate layers
  const layers = [];
  const stateGroups: Record<string, Rider[]> = {};

  for (const rider of riders) {
    const state = rider.trip_state || 'idle';
    if (!stateGroups[state]) stateGroups[state] = [];
    stateGroups[state].push(rider);
  }

  for (const [state, group] of Object.entries(stateGroups)) {
    if (group.length > 0) {
      layers.push(
        new IconLayer({
          id: `riders-${state}`,
          data: group,
          pickable: true,

          iconAtlas: getRiderIconUrl(),
          iconMapping: PERSON_ICON_MAPPING,
          getIcon: () => 'person',

          sizeMinPixels: 10,
          sizeMaxPixels: 24,
          getSize: 18 * scaleFactor,

          getPosition: (d: Rider) => [d.longitude, d.latitude],
          getColor:
            RIDER_TRIP_STATE_COLORS[state as TripStateValue] || RIDER_TRIP_STATE_COLORS.default,
        })
      );
    }
  }

  return layers;
}

export function createHomeMarkerLayer(
  homeLocation: [number, number] | null,
  scaleFactor: number = 1
) {
  const data = homeLocation ? [{ position: homeLocation }] : [];
  return new IconLayer({
    id: 'home-marker',
    data,
    pickable: false,

    iconAtlas: HOME_ICON,
    iconMapping: HOME_ICON_MAPPING,
    getIcon: () => 'home',

    sizeMinPixels: 28,
    sizeMaxPixels: 56,
    getSize: 42 * scaleFactor,

    getPosition: (d: { position: [number, number] }) => d.position,
    getColor: [236, 72, 153] as [number, number, number], // Vibrant pink (#EC4899)
  });
}
