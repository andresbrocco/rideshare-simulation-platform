import { IconLayer, PathLayer } from '@deck.gl/layers';
import type { Driver, Rider, Trip, TripStateValue } from '../types/api';

// Pre-colored icon URLs for deck.gl IconLayer (colored versions for reliable rendering)
const CAR_ICONS = {
  green: '/icons/car-green.png',
  gray: '/icons/car-gray.png',
  orange: '/icons/car-orange.png',
  yellow: '/icons/car-yellow.png',
  blue: '/icons/car-blue.png',
};

const PERSON_ICONS = {
  gray: '/icons/person-gray.png',
  orange: '/icons/person-orange.png',
  yellow: '/icons/person-yellow.png',
  lightblue: '/icons/person-lightblue.png',
  cyan: '/icons/person-cyan.png',
  purple: '/icons/person-purple.png',
};

// Checkered flag icon for trip destinations
const FLAG_ICON = '/icons/flag-checkered.png';
const FLAG_ICON_MAPPING = {
  flag: { x: 0, y: 0, width: 100, height: 100, anchorY: 100, anchorX: 0 },
};

// Icon mapping for deck.gl (defines icon bounds within the image)
const CAR_ICON_MAPPING = { car: { x: 0, y: 0, width: 100, height: 100, anchorY: 50, anchorX: 50 } };
const PERSON_ICON_MAPPING = {
  person: { x: 0, y: 0, width: 100, height: 100, anchorY: 50, anchorX: 50 },
};

// Driver status colors (for legend display)
export const DRIVER_COLORS: Record<string, [number, number, number]> = {
  online: [0, 255, 0], // Green - available
  offline: [128, 128, 128], // Gray - not active
  busy: [255, 165, 0], // Orange - matched but not yet en route
  en_route_pickup: [255, 215, 0], // Yellow/Gold - driving to pickup
  en_route_destination: [0, 100, 255], // Blue - with passenger
};

// Rider colors based on trip state
export const RIDER_TRIP_STATE_COLORS: Record<TripStateValue | 'default', [number, number, number]> =
  {
    offline: [192, 192, 192], // Light gray - no active request
    requested: [255, 165, 0], // Orange - trip requested
    offer_sent: [255, 165, 0], // Orange - offer sent to driver
    offer_expired: [255, 100, 100], // Light red - offer timed out
    offer_rejected: [255, 100, 100], // Light red - driver rejected
    matched: [255, 215, 0], // Yellow - driver assigned
    driver_en_route: [135, 206, 235], // Light blue - driver on the way
    driver_arrived: [0, 255, 255], // Cyan - driver at pickup
    started: [128, 0, 128], // Purple - in vehicle
    completed: [100, 200, 100], // Light green - trip completed
    cancelled: [200, 100, 100], // Dark red - trip cancelled
    default: [255, 165, 0], // Orange fallback
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

    iconAtlas: CAR_ICONS.green,
    iconMapping: CAR_ICON_MAPPING,
    getIcon: () => 'car',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 30 * scaleFactor,

    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getAngle: (d: Driver) => 90 - (d.heading ?? 0), // Rotate icon to face direction of travel

    // Tell deck.gl which accessor functions need recalculation
    updateTriggers: {
      getPosition: onlineDrivers.map((d) => `${d.id}:${d.latitude}:${d.longitude}`),
      getAngle: onlineDrivers.map((d) => `${d.id}:${d.heading}`),
    },
  });
}

export function createOfflineDriversLayer(drivers: Driver[], scaleFactor: number = 1) {
  const offlineDrivers = drivers.filter((d) => d.status === 'offline');
  return new IconLayer({
    id: 'offline-drivers',
    data: offlineDrivers,
    pickable: true,

    iconAtlas: CAR_ICONS.gray,
    iconMapping: CAR_ICON_MAPPING,
    getIcon: () => 'car',

    sizeMinPixels: 16,
    sizeMaxPixels: 32,
    getSize: 24 * scaleFactor,

    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getAngle: (d: Driver) => 90 - (d.heading ?? 0),
    getColor: [255, 255, 255, 200], // Slightly transparent for offline

    updateTriggers: {
      getPosition: offlineDrivers.map((d) => `${d.id}:${d.latitude}:${d.longitude}`),
      getAngle: offlineDrivers.map((d) => `${d.id}:${d.heading}`),
    },
  });
}

export function createBusyDriversLayer(drivers: Driver[], scaleFactor: number = 1) {
  const busyDrivers = drivers.filter((d) => d.status === 'busy');
  return new IconLayer({
    id: 'busy-drivers',
    data: busyDrivers,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: CAR_ICONS.orange,
    iconMapping: CAR_ICON_MAPPING,
    getIcon: () => 'car',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 30 * scaleFactor,

    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getAngle: (d: Driver) => 90 - (d.heading ?? 0),

    updateTriggers: {
      getPosition: busyDrivers.map((d) => `${d.id}:${d.latitude}:${d.longitude}`),
      getAngle: busyDrivers.map((d) => `${d.id}:${d.heading}`),
    },
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

    iconAtlas: CAR_ICONS.yellow,
    iconMapping: CAR_ICON_MAPPING,
    getIcon: () => 'car',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 30 * scaleFactor,

    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getAngle: (d: Driver) => 90 - (d.heading ?? 0),

    updateTriggers: {
      getPosition: enRoutePickupDrivers.map((d) => `${d.id}:${d.latitude}:${d.longitude}`),
      getAngle: enRoutePickupDrivers.map((d) => `${d.id}:${d.heading}`),
    },
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

    iconAtlas: CAR_ICONS.blue,
    iconMapping: CAR_ICON_MAPPING,
    getIcon: () => 'car',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 30 * scaleFactor,

    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getAngle: (d: Driver) => 90 - (d.heading ?? 0),

    updateTriggers: {
      getPosition: withPassengerDrivers.map((d) => `${d.id}:${d.latitude}:${d.longitude}`),
      getAngle: withPassengerDrivers.map((d) => `${d.id}:${d.heading}`),
    },
  });
}

export function createOfflineRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  const offlineRiders = riders.filter((r) => !r.trip_state || r.trip_state === 'offline');
  return new IconLayer({
    id: 'offline-riders',
    data: offlineRiders,
    pickable: true,

    iconAtlas: PERSON_ICONS.gray,
    iconMapping: PERSON_ICON_MAPPING,
    getIcon: () => 'person',

    sizeMinPixels: 20, // DEBUG: Increased from 14
    sizeMaxPixels: 40, // DEBUG: Increased from 28
    getSize: 30 * scaleFactor, // DEBUG: Increased from 20

    getPosition: (d: Rider) => [d.longitude, d.latitude],
    getColor: [255, 255, 255, 255], // DEBUG: Full opacity to test visibility

    updateTriggers: {
      getPosition: offlineRiders.map((r) => `${r.id}:${r.latitude}:${r.longitude}`),
    },
  });
}

export function createWaitingRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  // Riders in REQUESTED or OFFER_SENT states
  const waitingRiders = riders.filter(
    (r) => r.trip_state === 'requested' || r.trip_state === 'offer_sent'
  );
  return new IconLayer({
    id: 'waiting-riders',
    data: waitingRiders,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: PERSON_ICONS.orange,
    iconMapping: PERSON_ICON_MAPPING,
    getIcon: () => 'person',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 28 * scaleFactor,

    getPosition: (d: Rider) => [d.longitude, d.latitude],

    updateTriggers: {
      getPosition: waitingRiders.map((r) => `${r.id}:${r.latitude}:${r.longitude}`),
    },
  });
}

export function createMatchedRidersLayer(riders: Rider[], scaleFactor: number = 1) {
  // Riders in MATCHED state (driver just assigned)
  const matchedRiders = riders.filter((r) => r.trip_state === 'matched');
  return new IconLayer({
    id: 'matched-riders',
    data: matchedRiders,
    pickable: true,
    autoHighlight: true,
    highlightColor: [255, 255, 255, 128],

    iconAtlas: PERSON_ICONS.yellow,
    iconMapping: PERSON_ICON_MAPPING,
    getIcon: () => 'person',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 28 * scaleFactor,

    getPosition: (d: Rider) => [d.longitude, d.latitude],

    updateTriggers: {
      getPosition: matchedRiders.map((r) => `${r.id}:${r.latitude}:${r.longitude}`),
    },
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

    iconAtlas: PERSON_ICONS.lightblue,
    iconMapping: PERSON_ICON_MAPPING,
    getIcon: () => 'person',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 28 * scaleFactor,

    getPosition: (d: Rider) => [d.longitude, d.latitude],

    updateTriggers: {
      getPosition: enRouteRiders.map((r) => `${r.id}:${r.latitude}:${r.longitude}`),
    },
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

    iconAtlas: PERSON_ICONS.cyan,
    iconMapping: PERSON_ICON_MAPPING,
    getIcon: () => 'person',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 28 * scaleFactor,

    getPosition: (d: Rider) => [d.longitude, d.latitude],

    updateTriggers: {
      getPosition: arrivedRiders.map((r) => `${r.id}:${r.latitude}:${r.longitude}`),
    },
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

    iconAtlas: PERSON_ICONS.purple,
    iconMapping: PERSON_ICON_MAPPING,
    getIcon: () => 'person',

    sizeMinPixels: 20,
    sizeMaxPixels: 40,
    getSize: 28 * scaleFactor,

    getPosition: (d: Rider) => [d.longitude, d.latitude],

    updateTriggers: {
      getPosition: inTransitRiders.map((r) => `${r.id}:${r.latitude}:${r.longitude}`),
    },
  });
}

// Helper to swap coordinates from [lat, lon] to [lon, lat] for deck.gl
function swapCoordinates(route: [number, number][]): [number, number][] {
  return route.map(([lat, lon]) => [lon, lat]);
}

// Pending routes: Orange solid - trips waiting for driver match
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
    getColor: [255, 165, 0], // Orange - matches "waiting" rider color
    widthUnits: 'pixels',
    getWidth: 4 * scaleFactor,
  });
}

// Pickup routes: Pink/coral dashed - driver en route to pickup
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
    getColor: [255, 100, 150], // Pink/coral - distinct pickup route color
    widthUnits: 'pixels',
    getWidth: 4,
    getDashArray: [8, 4], // Dashed pattern
  });
}

// Trip routes: Blue solid - rider in vehicle (STARTED state only)
export function createPathLayer(trips: Trip[], visible: boolean = true) {
  const activeTrips = trips.filter((t) => t.route && t.route.length > 0 && t.status === 'started');

  return new PathLayer({
    id: 'trip-routes',
    data: activeTrips,
    visible,
    pickable: true,
    getPath: (d: Trip) => swapCoordinates(d.route),
    getColor: [0, 100, 255], // Blue - matches driver with passenger color
    widthUnits: 'pixels',
    getWidth: 5,
  });
}

// Completed pickup route trail: Faded pink/coral - portion already traveled
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
    getColor: [255, 100, 150, 80], // Faded pink/coral (~30% opacity)
    widthUnits: 'pixels',
    getWidth: 4 * scaleFactor,
    updateTriggers: {
      getPath: trailData.map((d) => d.trip.pickup_route_progress_index),
    },
  });
}

// Remaining pickup route: Solid pink/coral dashed - portion still to travel
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
    getColor: [255, 100, 150], // Solid pink/coral
    widthUnits: 'pixels',
    getWidth: 4 * scaleFactor,
    getDashArray: [8, 4], // Dashed pattern
    updateTriggers: {
      getPath: remainingData.map((d) => d.trip.pickup_route_progress_index),
    },
  });
}

// Completed trip route trail: Faded blue - portion already traveled
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
    getColor: [0, 100, 255, 80], // Faded blue (~30% opacity)
    widthUnits: 'pixels',
    getWidth: 5 * scaleFactor,
    updateTriggers: {
      getPath: trailData.map((d) => d.trip.route_progress_index),
    },
  });
}

// Remaining trip route: Solid blue - portion still to travel
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
    getColor: [0, 100, 255], // Solid blue
    widthUnits: 'pixels',
    getWidth: 5 * scaleFactor,
    updateTriggers: {
      getPath: remainingData.map((d) => d.trip.route_progress_index),
    },
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

    updateTriggers: {
      getPosition: activeTrips.map((t) => `${t.id}:${t.dropoff_latitude}:${t.dropoff_longitude}`),
    },
  });
}

// Helper to get driver icon based on status
function getDriverIconUrl(status: string): string {
  switch (status) {
    case 'online':
      return CAR_ICONS.green;
    case 'offline':
      return CAR_ICONS.gray;
    case 'busy':
      return CAR_ICONS.orange;
    case 'en_route_pickup':
      return CAR_ICONS.yellow;
    case 'en_route_destination':
      return CAR_ICONS.blue;
    default:
      return CAR_ICONS.green;
  }
}

export function createDriverLayer(drivers: Driver[], scaleFactor: number = 1) {
  // Group drivers by status for separate layers (since iconAtlas can't change per-item)
  const layers = [];
  const statusGroups = {
    online: drivers.filter((d) => d.status === 'online'),
    offline: drivers.filter((d) => d.status === 'offline'),
    busy: drivers.filter((d) => d.status === 'busy'),
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

          iconAtlas: getDriverIconUrl(status),
          iconMapping: CAR_ICON_MAPPING,
          getIcon: () => 'car',

          sizeMinPixels: 12,
          sizeMaxPixels: 30,
          getSize: 24 * scaleFactor,

          getPosition: (d: Driver) => [d.longitude, d.latitude],
          getAngle: (d: Driver) => 90 - (d.heading ?? 0),
        })
      );
    }
  }

  return layers;
}

// Helper to get rider icon based on trip state
function getRiderIconUrl(tripState: string | undefined): string {
  switch (tripState) {
    case 'offline':
      return PERSON_ICONS.gray;
    case 'requested':
    case 'offer_sent':
      return PERSON_ICONS.orange;
    case 'matched':
      return PERSON_ICONS.yellow;
    case 'driver_en_route':
      return PERSON_ICONS.lightblue;
    case 'driver_arrived':
      return PERSON_ICONS.cyan;
    case 'started':
      return PERSON_ICONS.purple;
    default:
      return PERSON_ICONS.gray;
  }
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

          iconAtlas: getRiderIconUrl(state),
          iconMapping: PERSON_ICON_MAPPING,
          getIcon: () => 'person',

          sizeMinPixels: 10,
          sizeMaxPixels: 24,
          getSize: 18 * scaleFactor,

          getPosition: (d: Rider) => [d.longitude, d.latitude],
        })
      );
    }
  }

  return layers;
}
