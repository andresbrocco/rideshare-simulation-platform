export interface LayerVisibility {
  // Driver layers
  onlineDrivers: boolean;
  offlineDrivers: boolean;
  enRoutePickupDrivers: boolean;
  withPassengerDrivers: boolean;
  repositioningDrivers: boolean;
  // Rider layers
  offlineRiders: boolean;
  requestingRiders: boolean;
  enRouteRiders: boolean;
  arrivedRiders: boolean;
  inTransitRiders: boolean;
  // Trip layers
  pendingRoutes: boolean; // Orange - requested but no driver matched
  pickupRoutes: boolean; // Yellow dashed - driver en route to pickup
  tripRoutes: boolean; // Blue solid - rider in vehicle
  matchingLines: boolean; // White blinking line — driver ↔ rider during offer phase
  // Zone layers
  zoneBoundaries: boolean;
  surgeHeatmap: boolean;
}

export const DEFAULT_VISIBILITY: LayerVisibility = {
  // Driver layers
  onlineDrivers: true,
  offlineDrivers: true,
  enRoutePickupDrivers: true,
  withPassengerDrivers: true,
  repositioningDrivers: true,
  // Rider layers
  offlineRiders: true,
  requestingRiders: true,
  enRouteRiders: true,
  arrivedRiders: true,
  inTransitRiders: true,
  // Trip layers
  pendingRoutes: true, // Show pending routes by default
  pickupRoutes: true, // Show pickup routes by default
  tripRoutes: true, // Show trip routes by default
  matchingLines: true,
  // Zone layers
  zoneBoundaries: true,
  surgeHeatmap: true,
};
