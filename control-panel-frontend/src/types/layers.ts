export interface LayerVisibility {
  onlineDrivers: boolean;
  offlineDrivers: boolean;
  busyDrivers: boolean;
  waitingRiders: boolean;
  inTransitRiders: boolean;
  tripRoutes: boolean;
  gpsTrails: boolean;
  zoneBoundaries: boolean;
  surgeHeatmap: boolean;
}

export const DEFAULT_VISIBILITY: LayerVisibility = {
  onlineDrivers: true,
  offlineDrivers: false,
  busyDrivers: true,
  waitingRiders: true,
  inTransitRiders: true,
  tripRoutes: true,
  gpsTrails: true,
  zoneBoundaries: true,
  surgeHeatmap: false,
};
