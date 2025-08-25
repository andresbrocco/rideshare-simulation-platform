import { useMemo } from 'react';
import type { Layer } from '@deck.gl/core';
import type { Driver, Rider, Trip, GPSTrail, ZoneData, DemandPoint } from '../types/api';
import {
  createDriverLayer,
  createRiderLayer,
  createTripsLayer,
  createPathLayer,
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
  showZones?: boolean;
  showHeatmap?: boolean;
}

export function useSimulationLayers({
  drivers,
  riders,
  trips,
  trails,
  currentTime,
  zoneData = [],
  demandPoints = [],
  showZones = true,
  showHeatmap = false,
}: UseSimulationLayersProps): Layer[] {
  return useMemo(() => {
    const layers: Layer[] = [];

    if (zoneData.length > 0) {
      layers.push(createZoneLayer(zoneData, showZones));
    }

    if (demandPoints.length > 0) {
      layers.push(createHeatmapLayer(demandPoints, showHeatmap));
    }

    layers.push(
      createTripsLayer(trails, currentTime),
      createPathLayer(trips),
      createDriverLayer(drivers),
      createRiderLayer(riders)
    );

    return layers;
  }, [drivers, riders, trips, trails, currentTime, zoneData, demandPoints, showZones, showHeatmap]);
}
