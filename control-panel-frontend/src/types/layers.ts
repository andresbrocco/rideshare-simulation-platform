export interface LayerVisibility {
  // Driver layers
  onlineDrivers: boolean;
  offlineDrivers: boolean;
  busyDrivers: boolean;
  enRoutePickupDrivers: boolean;
  withPassengerDrivers: boolean;
  // Rider layers
  offlineRiders: boolean;
  waitingRiders: boolean;
  matchedRiders: boolean;
  enRouteRiders: boolean;
  arrivedRiders: boolean;
  inTransitRiders: boolean;
  // Trip layers
  pendingRoutes: boolean; // Orange - requested but no driver matched
  pickupRoutes: boolean; // Yellow dashed - driver en route to pickup
  tripRoutes: boolean; // Blue solid - rider in vehicle
  // Zone layers
  zoneBoundaries: boolean;
  surgeHeatmap: boolean;
}

export const DEFAULT_VISIBILITY: LayerVisibility = {
  // Driver layers
  onlineDrivers: true,
  offlineDrivers: true,
  busyDrivers: true,
  enRoutePickupDrivers: true,
  withPassengerDrivers: true,
  // Rider layers
  offlineRiders: true,
  waitingRiders: true,
  matchedRiders: true,
  enRouteRiders: true,
  arrivedRiders: true,
  inTransitRiders: true,
  // Trip layers
  pendingRoutes: true, // Show pending routes by default
  pickupRoutes: true, // Show pickup routes by default
  tripRoutes: true, // Show trip routes by default
  // Zone layers
  zoneBoundaries: true,
  surgeHeatmap: true,
};
