import { PathLayer } from '@deck.gl/layers';
import type { Trip } from '../types/api';

export function createTripLayer(trips: Trip[]) {
  return new PathLayer({
    id: 'trips',
    data: trips,
    getPath: (t: Trip) => t.route,
    getColor: [96, 165, 250, 200],
    getWidth: 3,
    widthMinPixels: 2,
    pickable: true,
  });
}
