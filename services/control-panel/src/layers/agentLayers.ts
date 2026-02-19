import { IconLayer, PathLayer } from '@deck.gl/layers';
import type { Driver, Rider, Trip, TripStateValue } from '../types/api';

// Monochrome white icons — deck.gl getColor tinting provides phase-based colors
const CAR_ICON = '/icons/car.png';
const PERSON_ICON = '/icons/person.png';

// Checkered flag icon for trip destinations
const FLAG_ICON = '/icons/flag-checkered.png';
const FLAG_ICON_MAPPING = {
  flag: { x: 0, y: 0, width: 100, height: 100, anchorY: 100, anchorX: 0 },
};

// Icon mapping for deck.gl (defines icon bounds within the image)
const CAR_ICON_MAPPING = {
  car: { x: 0, y: 0, width: 100, height: 100, anchorY: 50, anchorX: 50, mask: true },
};
const PERSON_ICON_MAPPING = {
  person: { x: 0, y: 0, width: 100, height: 100, anchorY: 50, anchorX: 50, mask: true },
};

// Driver status colors by trip lifecycle phase
export const DRIVER_COLORS: Record<string, [number, number, number]> = {
  online: [52, 211, 153], // Emerald - available
  offline: [107, 114, 128], // Gray - idle
  en_route_pickup: [245, 158, 11], // Amber - pickup phase
  en_route_destination: [59, 130, 246], // Blue - in transit
};

// Rider colors by trip lifecycle phase
export const RIDER_TRIP_STATE_COLORS: Record<TripStateValue | 'default', [number, number, number]> =
  {
    offline: [156, 163, 175], // Light gray - idle
    requested: [249, 115, 22], // Orange - requesting
    offer_sent: [249, 115, 22], // Orange - requesting
    offer_expired: [248, 113, 113], // Red - terminal failure
    offer_rejected: [248, 113, 113], // Red - terminal failure
    matched: [245, 158, 11], // Amber - pickup phase
    driver_en_route: [251, 191, 36], // Gold - pickup progression
    driver_arrived: [253, 224, 71], // Yellow - pickup ready
    started: [59, 130, 246], // Blue - in transit
    completed: [74, 222, 128], // Green - terminal success
    cancelled: [248, 113, 113], // Red - terminal failure
    default: [249, 115, 22], // Orange fallback
  };

// Helper to get rider color from trip state
export function getRiderColor(rider: Rider): [number, number, number] {
  const tripState = rider.trip_state || 'offline';
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
  const onlineDrivers = drivers.filter((d) => d.status === 'online');
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
    getColor: [52, 211, 153], // Emerald - available phase
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
    getColor: [107, 114, 128, 200], // Gray - idle phase, slightly transparent
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
    getColor: [245, 158, 11], // Amber - pickup phase
  });
}

export function createWithPassengerDriversLayer(drivers: Driver[], scaleFactor: number = 1) {
  const withPassengerDrivers = drivers.filter((d) => d.status === 'en_route_destination');
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
    getColor: [59, 130, 246], // Blue - in transit phase
  });
}

// Trip states that have their own dedicated rider layers
const ACTIVE_TRIP_STATES = new Set<string>([
  'requested',
  'offer_sent',
  'matched',
  'driver_en_route',
  'driver_arrived',
  'started',
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
    getColor: [156, 163, 175], // Light gray - idle phase
  });
}

export function createRequestingRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  // Riders in REQUESTED, OFFER_SENT, or MATCHED states (pre-pickup phase)
  const requestingRiders = riders.filter(
    (r) =>
      r.trip_state === 'requested' || r.trip_state === 'offer_sent' || r.trip_state === 'matched'
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
    getColor: [249, 115, 22], // Orange - requesting phase
  });
}

export function createEnRouteRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  // Riders in DRIVER_EN_ROUTE state (driver on the way)
  const enRouteRiders = riders.filter((r) => r.trip_state === 'driver_en_route');
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
    getColor: [251, 191, 36], // Gold - pickup progression
  });
}

export function createArrivedRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  // Riders in DRIVER_ARRIVED state (driver at pickup location)
  const arrivedRiders = riders.filter((r) => r.trip_state === 'driver_arrived');
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
    getColor: [253, 224, 71], // Yellow - pickup ready
  });
}

export function createInTransitRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  // Riders in STARTED state (in vehicle)
  const inTransitRiders = riders.filter((r) => r.trip_state === 'started');
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
    getColor: [59, 130, 246], // Blue - in transit phase
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
      (t.status === 'requested' || t.status === 'offer_sent' || t.status === 'matched')
  );

  return new PathLayer({
    id: 'pending-routes',
    data: pendingTrips,
    visible,
    pickable: true,
    getPath: (d: Trip) => swapCoordinates(d.route),
    getColor: [253, 186, 116], // Light orange - requesting phase
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
      (t.status === 'driver_en_route' || t.status === 'driver_arrived')
  );

  return new PathLayer({
    id: 'pickup-routes',
    data: tripsWithPickupRoutes,
    visible,
    pickable: true,
    getPath: (d: Trip) => swapCoordinates(d.pickup_route),
    getColor: [252, 211, 77], // Gold - pickup phase
    widthUnits: 'pixels',
    getWidth: 4,
    getDashArray: [8, 4], // Dashed pattern
  });
}

// Trip routes: Light blue solid - in transit phase
export function createPathLayer(trips: Trip[], visible: boolean = true) {
  const activeTrips = trips.filter((t) => t.route && t.route.length > 0 && t.status === 'started');

  return new PathLayer({
    id: 'trip-routes',
    data: activeTrips,
    visible,
    pickable: true,
    getPath: (d: Trip) => swapCoordinates(d.route),
    getColor: [96, 165, 250], // Light blue - in transit phase
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
      t.status === 'driver_en_route' &&
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
    getColor: [252, 211, 77, 80], // Faded gold (~30% opacity)
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
  // Only show during driver_en_route - once arrived, pickup route is complete
  const tripsWithPickupRoutes = trips.filter(
    (t) => t.pickup_route && t.pickup_route.length > 0 && t.status === 'driver_en_route'
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
    getColor: [252, 211, 77], // Solid gold - pickup phase
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
      t.status === 'started' &&
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
    getColor: [96, 165, 250, 80], // Faded light blue (~30% opacity)
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
  const activeTrips = trips.filter((t) => t.route && t.route.length > 0 && t.status === 'started');

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
    getColor: [96, 165, 250], // Solid light blue - in transit phase
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
  const activeTrips = trips.filter((t) => t.route && t.route.length > 0 && t.status === 'started');

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
    online: drivers.filter((d) => d.status === 'online'),
    offline: drivers.filter((d) => d.status === 'offline'),
    en_route_pickup: drivers.filter((d) => d.status === 'en_route_pickup'),
    en_route_destination: drivers.filter((d) => d.status === 'en_route_destination'),
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
          getColor: DRIVER_COLORS[status] || DRIVER_COLORS.online,
        })
      );
    }
  }

  return layers;
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
    const state = rider.trip_state || 'offline';
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
