import { PolygonLayer } from '@deck.gl/layers';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import type { ZoneData, DemandPoint } from '../types/api';
import { surgeToColor, getSurgeOpacity } from '../utils/colorScale';

export function createZoneLayer(zones: ZoneData[], visible: boolean) {
  return new PolygonLayer({
    id: 'zones',
    data: zones,
    pickable: true,
    stroked: true,
    filled: true,
    visible,
    lineWidthMinPixels: 2,
    getPolygon: (d: ZoneData) => d.feature.geometry.coordinates,
    getFillColor: (d: ZoneData) => {
      const rgb = surgeToColor(d.surge);
      const opacity = getSurgeOpacity(d.surge);
      return [...rgb, Math.round(opacity * 255)];
    },
    getLineColor: [255, 255, 255, 100],
    updateTriggers: {
      getFillColor: [zones.map((z) => z.surge)],
    },
  });
}

export function createHeatmapLayer(demandPoints: DemandPoint[], visible: boolean) {
  return new HeatmapLayer({
    id: 'demand-heatmap',
    data: demandPoints,
    visible,
    radiusPixels: 60,
    getPosition: (d: DemandPoint) => [d.longitude, d.latitude],
    getWeight: (d: DemandPoint) => d.weight,
    colorRange: [
      [255, 255, 178],
      [254, 217, 118],
      [254, 178, 76],
      [253, 141, 60],
      [240, 59, 32],
      [189, 0, 38],
    ],
  });
}

export function getZoneTooltipData(zone: ZoneData): string {
  const { name, subprefecture } = zone.feature.properties;
  const { surge, driver_count } = zone;

  return `
    <div>
      <strong>${name}</strong>
      ${subprefecture ? `<br/>${subprefecture}` : ''}
      <br/>Surge: ${surge.toFixed(1)}x
      <br/>Drivers: ${driver_count}
    </div>
  `;
}
