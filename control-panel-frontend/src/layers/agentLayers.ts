import { ScatterplotLayer } from '@deck.gl/layers';
import type { Driver, Rider } from '../types/api';

export function createDriverLayer(drivers: Driver[]) {
  return new ScatterplotLayer({
    id: 'drivers',
    data: drivers,
    getPosition: (d: Driver) => [d.longitude, d.latitude],
    getFillColor: (d: Driver) => {
      switch (d.status) {
        case 'online':
          return [0, 255, 0, 200];
        case 'busy':
          return [255, 165, 0, 200];
        case 'en_route':
          return [0, 0, 255, 200];
        default:
          return [128, 128, 128, 200];
      }
    },
    getRadius: 50,
    radiusMinPixels: 3,
    radiusMaxPixels: 10,
    pickable: true,
  });
}

export function createRiderLayer(riders: Rider[]) {
  return new ScatterplotLayer({
    id: 'riders',
    data: riders,
    getPosition: (r: Rider) => [r.longitude, r.latitude],
    getFillColor: [255, 0, 0, 200],
    getRadius: 40,
    radiusMinPixels: 2,
    radiusMaxPixels: 8,
    pickable: true,
  });
}
