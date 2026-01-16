import { PathLayer } from '@deck.gl/layers';
import type { Trip } from '../types/api';

export function createTripLayer(trips: Trip[]) {
  return new PathLayer({
    id: 'trips',
    data: trips,
    getPath: (t: Trip) => t.route,
    getColor: [0, 100, 255, 200],
    getWidth: 3,
    widthMinPixels: 2,
    pickable: true,
  });
}
