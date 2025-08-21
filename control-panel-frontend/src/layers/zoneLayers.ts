import { PolygonLayer } from '@deck.gl/layers';

interface Zone {
  id: string;
  coordinates: number[][][];
}

export function createZoneLayer(zones: Zone[], surgeData: Record<string, number>) {
  return new PolygonLayer({
    id: 'zones',
    data: zones,
    getPolygon: (d: Zone) => d.coordinates,
    getFillColor: (d: Zone) => {
      const surge = surgeData[d.id] || 1.0;
      const intensity = Math.min((surge - 1.0) / 1.5, 1.0);
      return [255 * intensity, 0, 0, 80];
    },
    getLineColor: [80, 80, 80, 200],
    getLineWidth: 20,
    lineWidthMinPixels: 1,
    pickable: true,
  });
}
