import { useMemo } from 'react';
import type { Layer } from '@deck.gl/core';
import type { Driver, Rider, Trip, GPSTrail, ZoneData, DemandPoint } from '../types/api';
import type { LayerVisibility } from '../types/layers';
import {
  createOnlineDriversLayer,
  createOfflineDriversLayer,
  createBusyDriversLayer,
  createWaitingRidersLayer,
  createInTransitRidersLayer,
  createTripsLayer,
  createPathLayer,
  createDriverLayer,
  createRiderLayer,
} from '../layers/agentLayers';
import { createZoneLayer, createHeatmapLayer } from '../layers/zoneLayers';

interface UseSimulationLayersProps {
  drivers: Driver[];
  riders: Rider[];
  trips: Trip[];
  trails: GPSTrail[];
  currentTime: number;
  zoneData?: ZoneData[];
  demandPoints?: DemandPoint[];
  layerVisibility?: LayerVisibility;
}

export function useSimulationLayers({
  drivers,
  riders,
  trips,
  trails,
  currentTime,
  zoneData = [],
  demandPoints = [],
  layerVisibility,
}: UseSimulationLayersProps): Layer[] {
  return useMemo(() => {
    const layers: Layer[] = [];

    if (layerVisibility) {
      if (layerVisibility.zoneBoundaries && zoneData.length > 0) {
        layers.push(createZoneLayer(zoneData, true));
      }

      if (layerVisibility.surgeHeatmap && demandPoints.length > 0) {
        layers.push(createHeatmapLayer(demandPoints, true));
      }

      if (layerVisibility.gpsTrails) {
        layers.push(createTripsLayer(trails, currentTime, true));
      }

      if (layerVisibility.tripRoutes) {
        layers.push(createPathLayer(trips, true));
      }

      if (layerVisibility.onlineDrivers) {
        layers.push(createOnlineDriversLayer(drivers));
      }

      if (layerVisibility.offlineDrivers) {
        layers.push(createOfflineDriversLayer(drivers));
      }

      if (layerVisibility.busyDrivers) {
        layers.push(createBusyDriversLayer(drivers));
      }

      if (layerVisibility.waitingRiders) {
        layers.push(createWaitingRidersLayer(riders));
      }

      if (layerVisibility.inTransitRiders) {
        layers.push(createInTransitRidersLayer(riders));
      }
    } else {
      if (zoneData.length > 0) {
        layers.push(createZoneLayer(zoneData, true));
      }

      if (demandPoints.length > 0) {
        layers.push(createHeatmapLayer(demandPoints, false));
      }

      layers.push(
        createTripsLayer(trails, currentTime),
        createPathLayer(trips),
        createDriverLayer(drivers),
        createRiderLayer(riders)
      );
    }

    return layers;
  }, [drivers, riders, trips, trails, currentTime, zoneData, demandPoints, layerVisibility]);
}
