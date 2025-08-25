import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useSimulationLayers } from '../useSimulationLayers';
import type { Driver, Rider, Trip, ZoneData, DemandPoint } from '../../types/api';

describe('useSimulationLayers', () => {
  it('returns array of layers in correct order without zones', () => {
    const drivers: Driver[] = [
      { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
    ];
    const riders: Rider[] = [{ id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting' }];
    const trips: Trip[] = [];

    const { result } = renderHook(() =>
      useSimulationLayers({
        drivers,
        riders,
        trips,
        trails: [],
        currentTime: 0,
      })
    );

    expect(result.current).toHaveLength(4);
    expect(result.current[0].id).toBe('gps-trails');
    expect(result.current[1].id).toBe('trip-routes');
    expect(result.current[2].id).toBe('drivers');
    expect(result.current[3].id).toBe('riders');
  });

  it('returns array of layers with zones in correct order', () => {
    const drivers: Driver[] = [
      { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
    ];
    const riders: Rider[] = [{ id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting' }];
    const trips: Trip[] = [];
    const zoneData: ZoneData[] = [
      {
        feature: {
          type: 'Feature',
          properties: { name: 'Zone A', zone_id: 'ZA' },
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
        surge: 1.5,
        driver_count: 10,
      },
    ];

    const { result } = renderHook(() =>
      useSimulationLayers({
        drivers,
        riders,
        trips,
        trails: [],
        currentTime: 0,
        zoneData,
        showZones: true,
      })
    );

    expect(result.current).toHaveLength(5);
    expect(result.current[0].id).toBe('zones');
    expect(result.current[1].id).toBe('gps-trails');
    expect(result.current[2].id).toBe('trip-routes');
    expect(result.current[3].id).toBe('drivers');
    expect(result.current[4].id).toBe('riders');
  });

  it('returns array of layers with zones and heatmap in correct order', () => {
    const drivers: Driver[] = [];
    const riders: Rider[] = [];
    const trips: Trip[] = [];
    const zoneData: ZoneData[] = [
      {
        feature: {
          type: 'Feature',
          properties: { name: 'Zone A', zone_id: 'ZA' },
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
        surge: 1.5,
        driver_count: 10,
      },
    ];
    const demandPoints: DemandPoint[] = [{ latitude: -23.5, longitude: -46.6, weight: 1.5 }];

    const { result } = renderHook(() =>
      useSimulationLayers({
        drivers,
        riders,
        trips,
        trails: [],
        currentTime: 0,
        zoneData,
        demandPoints,
        showZones: true,
        showHeatmap: true,
      })
    );

    expect(result.current).toHaveLength(6);
    expect(result.current[0].id).toBe('zones');
    expect(result.current[1].id).toBe('demand-heatmap');
    expect(result.current[2].id).toBe('gps-trails');
  });

  it('handles empty data arrays', () => {
    const { result } = renderHook(() =>
      useSimulationLayers({
        drivers: [],
        riders: [],
        trips: [],
        trails: [],
        currentTime: 0,
      })
    );

    expect(result.current).toHaveLength(4);
  });
});
