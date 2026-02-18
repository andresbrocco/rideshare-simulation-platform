import { useMemo } from 'react';
import type { Layer } from '@deck.gl/core';
import type { Driver, Rider, Trip, ZoneData, DemandPoint } from '../types/api';
import type { LayerVisibility } from '../types/layers';
import { calculateZoomScale } from '../utils/zoomScale';
import {
  createOnlineDriversLayer,
  createOfflineDriversLayer,
  createEnRoutePickupDriversLayer,
  createWithPassengerDriversLayer,
  createOfflineRidersLayer,
  createWaitingRidersLayer,
  createMatchedRidersLayer,
  createEnRouteRidersLayer,
  createArrivedRidersLayer,
  createInTransitRidersLayer,
  createPendingRouteLayer,
  createCompletedPickupRouteLayer,
  createRemainingPickupRouteLayer,
  createCompletedTripRouteLayer,
  createRemainingTripRouteLayer,
  createDestinationFlagLayer,
  createDriverLayer,
  createRiderLayer,
} from '../layers/agentLayers';
import { createZoneLayer, createHeatmapLayer } from '../layers/zoneLayers';

interface UseSimulationLayersProps {
  drivers: Driver[];
  riders: Rider[];
  trips: Trip[];
  zoneData?: ZoneData[];
  demandPoints?: DemandPoint[];
  layerVisibility?: LayerVisibility;
  zoom?: number;
}

export function useSimulationLayers({
  drivers,
  riders,
  trips,
  zoneData = [],
  demandPoints = [],
  layerVisibility,
  zoom = 11,
}: UseSimulationLayersProps): Layer[] {
  return useMemo(() => {
    const scaleFactor = calculateZoomScale(zoom);
    const layers: Layer[] = [];

    if (layerVisibility) {
      // Add zone layer first (lowest pick priority)
      if (layerVisibility.zoneBoundaries && zoneData.length > 0) {
        layers.push(createZoneLayer(zoneData, true));
      }

      if (layerVisibility.surgeHeatmap && demandPoints.length > 0) {
        layers.push(createHeatmapLayer(demandPoints, true));
      }

      // Route layers (ordered: pending -> pickup trail -> pickup remaining -> trip trail -> trip remaining)
      // Faded trails render first (behind), then solid remaining routes on top
      if (layerVisibility.pendingRoutes) {
        layers.push(createPendingRouteLayer(trips, true, scaleFactor));
      }

      if (layerVisibility.pickupRoutes) {
        // Completed portion (faded trail behind driver)
        layers.push(createCompletedPickupRouteLayer(trips, true, scaleFactor));
        // Remaining portion (solid ahead of driver)
        layers.push(createRemainingPickupRouteLayer(trips, true, scaleFactor));
      }

      if (layerVisibility.tripRoutes) {
        // Completed portion (faded trail behind driver)
        layers.push(createCompletedTripRouteLayer(trips, true, scaleFactor));
        // Remaining portion (solid ahead of driver)
        layers.push(createRemainingTripRouteLayer(trips, true, scaleFactor));
        // Destination flag at dropoff location
        layers.push(createDestinationFlagLayer(trips, true, scaleFactor));
      }

      // Add agent layers last (highest pick priority) so clicking on agents works
      // Driver layers (ordered by visual priority - active on top)
      if (layerVisibility.offlineDrivers) {
        layers.push(createOfflineDriversLayer(drivers, scaleFactor));
      }

      if (layerVisibility.enRoutePickupDrivers) {
        layers.push(createEnRoutePickupDriversLayer(drivers, scaleFactor));
      }

      if (layerVisibility.withPassengerDrivers) {
        layers.push(createWithPassengerDriversLayer(drivers, scaleFactor));
      }

      if (layerVisibility.onlineDrivers) {
        layers.push(createOnlineDriversLayer(drivers, scaleFactor));
      }

      // Rider layers (ordered by visual priority - active on top)
      if (layerVisibility.offlineRiders) {
        layers.push(createOfflineRidersLayer(riders, scaleFactor));
      }

      if (layerVisibility.waitingRiders) {
        layers.push(createWaitingRidersLayer(riders, scaleFactor));
      }

      if (layerVisibility.matchedRiders) {
        layers.push(createMatchedRidersLayer(riders, scaleFactor));
      }

      if (layerVisibility.enRouteRiders) {
        layers.push(createEnRouteRidersLayer(riders, scaleFactor));
      }

      if (layerVisibility.arrivedRiders) {
        layers.push(createArrivedRidersLayer(riders, scaleFactor));
      }

      if (layerVisibility.inTransitRiders) {
        layers.push(createInTransitRidersLayer(riders, scaleFactor));
      }
    } else {
      if (zoneData.length > 0) {
        layers.push(createZoneLayer(zoneData, true));
      }

      if (demandPoints.length > 0) {
        layers.push(createHeatmapLayer(demandPoints, false));
      }

      layers.push(
        createPendingRouteLayer(trips, true, scaleFactor),
        createCompletedPickupRouteLayer(trips, true, scaleFactor),
        createRemainingPickupRouteLayer(trips, true, scaleFactor),
        createCompletedTripRouteLayer(trips, true, scaleFactor),
        createRemainingTripRouteLayer(trips, true, scaleFactor),
        createDestinationFlagLayer(trips, true, scaleFactor),
        ...createDriverLayer(drivers, scaleFactor),
        ...createRiderLayer(riders, scaleFactor)
      );
    }

    return layers;
  }, [drivers, riders, trips, zoneData, demandPoints, layerVisibility, zoom]);
}
