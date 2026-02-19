import { PathLayer } from '@deck.gl/layers';
import type { Trip } from '../types/api';
import { STAGE_RGB } from '../theme';

export function createTripLayer(trips: Trip[]) {
  return new PathLayer({
    id: 'trips',
    data: trips,
    getPath: (t: Trip) => t.route,
    getColor: [...STAGE_RGB.transit.route, 200],
    getWidth: 3,
    widthMinPixels: 2,
    pickable: true,
  });
}
