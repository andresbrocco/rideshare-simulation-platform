import { useMemo } from 'react';
import type { Layer } from '@deck.gl/core';
import type { Driver, Rider, Trip, GPSTrail } from '../types/api';
import {
  createDriverLayer,
  createRiderLayer,
  createTripsLayer,
  createPathLayer,
} from '../layers/agentLayers';

interface UseSimulationLayersProps {
  drivers: Driver[];
  riders: Rider[];
  trips: Trip[];
  trails: GPSTrail[];
  currentTime: number;
}

export function useSimulationLayers({
  drivers,
  riders,
  trips,
  trails,
  currentTime,
}: UseSimulationLayersProps): Layer[] {
  return useMemo(() => {
    return [
      createTripsLayer(trails, currentTime),
      createPathLayer(trips),
      createDriverLayer(drivers),
      createRiderLayer(riders),
    ];
  }, [drivers, riders, trips, trails, currentTime]);
}
