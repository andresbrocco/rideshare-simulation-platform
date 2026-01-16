import { describe, it, expect } from 'vitest';
import { PolygonLayer } from '@deck.gl/layers';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import type { ZoneData, DemandPoint } from '../../types/api';
import { createZoneLayer, createHeatmapLayer, getZoneTooltipData } from '../zoneLayers';
import { surgeToColor, getSurgeOpacity } from '../../utils/colorScale';

describe('zoneLayers', () => {
  describe('createZoneLayer', () => {
    it('test_create_zone_layer', () => {
      const zones: ZoneData[] = [
        {
          feature: {
            type: 'Feature',
            properties: {
              name: 'PINHEIROS',
              zone_id: 'PIN',
              subprefecture: 'PINHEIROS',
              demand_multiplier: 1.7,
              surge_sensitivity: 0.9,
            },
            geometry: {
              type: 'Polygon',
              coordinates: [
                [
                  [-46.7, -23.57],
                  [-46.69, -23.58],
                  [-46.67, -23.57],
                  [-46.7, -23.57],
                ],
              ],
            },
          },
          surge: 1.5,
          driver_count: 25,
        },
      ];

      const layer = createZoneLayer(zones, true);

      expect(layer).toBeInstanceOf(PolygonLayer);
      expect(layer.id).toBe('zones');
      expect(layer.props.data).toBe(zones);
      expect(layer.props.visible).toBe(true);
    });

    it('test_zone_layer_pickable', () => {
      const zones: ZoneData[] = [];
      const layer = createZoneLayer(zones, true);

      expect(layer.props.pickable).toBe(true);
    });

    it('test_zone_boundaries_visible', () => {
      const zones: ZoneData[] = [];
      const layer = createZoneLayer(zones, true);

      expect(layer.props.stroked).toBe(true);
      expect(layer.props.lineWidthMinPixels).toBe(2);
    });

    it('test_zone_coloring_by_surge', () => {
      const zones: ZoneData[] = [
        {
          feature: {
            type: 'Feature',
            properties: {
              name: 'Zone A',
              zone_id: 'ZA',
            },
            geometry: {
              type: 'Polygon',
              coordinates: [
                [
                  [0, 0],
                  [1, 0],
                  [1, 1],
                  [0, 1],
                  [0, 0],
                ],
              ],
            },
          },
          surge: 1.0,
          driver_count: 10,
        },
        {
          feature: {
            type: 'Feature',
            properties: {
              name: 'Zone B',
              zone_id: 'ZB',
            },
            geometry: {
              type: 'Polygon',
              coordinates: [
                [
                  [0, 0],
                  [1, 0],
                  [1, 1],
                  [0, 1],
                  [0, 0],
                ],
              ],
            },
          },
          surge: 2.5,
          driver_count: 5,
        },
      ];

      const layer = createZoneLayer(zones, true);
      const getFillColor = layer.props.getFillColor as (d: ZoneData) => number[];

      const color1 = getFillColor(zones[0]);
      const color2 = getFillColor(zones[1]);

      expect(color1.length).toBe(4);
      expect(color2.length).toBe(4);
      expect(color1[0]).toBeLessThan(color2[0]);
    });

    it('test_surge_color_interpolation', () => {
      const lowSurge: ZoneData = {
        feature: {
          type: 'Feature',
          properties: { name: 'Low', zone_id: 'L' },
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [0, 0],
                [1, 0],
                [1, 1],
                [0, 0],
              ],
            ],
          },
        },
        surge: 1.0,
        driver_count: 10,
      };

      const midSurge: ZoneData = {
        feature: {
          type: 'Feature',
          properties: { name: 'Mid', zone_id: 'M' },
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [0, 0],
                [1, 0],
                [1, 1],
                [0, 0],
              ],
            ],
          },
        },
        surge: 1.75,
        driver_count: 7,
      };

      const highSurge: ZoneData = {
        feature: {
          type: 'Feature',
          properties: { name: 'High', zone_id: 'H' },
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [0, 0],
                [1, 0],
                [1, 1],
                [0, 0],
              ],
            ],
          },
        },
        surge: 2.5,
        driver_count: 3,
      };

      const lowColor = surgeToColor(lowSurge.surge);
      const midColor = surgeToColor(midSurge.surge);
      const highColor = surgeToColor(highSurge.surge);

      expect(lowColor[1]).toBe(255);
      expect(midColor[0]).toBeGreaterThan(0);
      expect(midColor[1]).toBeGreaterThan(0);
      expect(highColor[0]).toBe(255);
    });

    it('test_zone_visibility_toggle', () => {
      const zones: ZoneData[] = [];
      const visibleLayer = createZoneLayer(zones, true);
      const hiddenLayer = createZoneLayer(zones, false);

      expect(visibleLayer.props.visible).toBe(true);
      expect(hiddenLayer.props.visible).toBe(false);
    });

    it('test_empty_zones_handling', () => {
      const layer = createZoneLayer([], true);

      expect(layer).toBeInstanceOf(PolygonLayer);
      expect(layer.props.data).toEqual([]);
    });
  });

  describe('createHeatmapLayer', () => {
    it('test_create_heatmap_layer', () => {
      const demandPoints: DemandPoint[] = [
        { latitude: -23.5, longitude: -46.6, weight: 1.5 },
        { latitude: -23.55, longitude: -46.65, weight: 2.0 },
      ];

      const layer = createHeatmapLayer(demandPoints, true);

      expect(layer).toBeInstanceOf(HeatmapLayer);
      expect(layer.id).toBe('demand-heatmap');
      expect(layer.props.data).toBe(demandPoints);
    });

    it('test_heatmap_visibility_toggle', () => {
      const demandPoints: DemandPoint[] = [];
      const visibleLayer = createHeatmapLayer(demandPoints, true);
      const hiddenLayer = createHeatmapLayer(demandPoints, false);

      expect(visibleLayer.props.visible).toBe(true);
      expect(hiddenLayer.props.visible).toBe(false);
    });

    it('test_heatmap_radius', () => {
      const demandPoints: DemandPoint[] = [];
      const layer = createHeatmapLayer(demandPoints, true);

      expect(layer.props.radiusPixels).toBe(60);
    });
  });

  describe('getZoneTooltipData', () => {
    it('test_zone_tooltip_content', () => {
      const zone: ZoneData = {
        feature: {
          type: 'Feature',
          properties: {
            name: 'PINHEIROS',
            zone_id: 'PIN',
            subprefecture: 'PINHEIROS',
          },
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [0, 0],
                [1, 0],
                [1, 1],
                [0, 0],
              ],
            ],
          },
        },
        surge: 1.8,
        driver_count: 42,
      };

      const tooltip = getZoneTooltipData(zone);

      expect(tooltip).toContain('PINHEIROS');
      expect(tooltip).toContain('1.8');
      expect(tooltip).toContain('42');
    });

    it('test_zone_tooltip_handles_missing_subprefecture', () => {
      const zone: ZoneData = {
        feature: {
          type: 'Feature',
          properties: {
            name: 'TEST ZONE',
            zone_id: 'TST',
          },
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [0, 0],
                [1, 0],
                [1, 1],
                [0, 0],
              ],
            ],
          },
        },
        surge: 1.2,
        driver_count: 10,
      };

      const tooltip = getZoneTooltipData(zone);

      expect(tooltip).toContain('TEST ZONE');
      expect(tooltip).toContain('1.2');
    });
  });

  describe('surge opacity', () => {
    it('test_surge_opacity_range', () => {
      const lowOpacity = getSurgeOpacity(1.0);
      const midOpacity = getSurgeOpacity(1.75);
      const highOpacity = getSurgeOpacity(2.5);

      expect(lowOpacity).toBe(0.2);
      expect(midOpacity).toBeGreaterThan(lowOpacity);
      expect(midOpacity).toBeLessThan(highOpacity);
      expect(highOpacity).toBeCloseTo(0.6, 5);
    });
  });
});
