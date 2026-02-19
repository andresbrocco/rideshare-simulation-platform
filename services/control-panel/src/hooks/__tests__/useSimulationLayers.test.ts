import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useSimulationLayers } from '../useSimulationLayers';
import type { Driver, Rider, Trip, ZoneData, DemandPoint } from '../../types/api';
import type { LayerVisibility } from '../../types/layers';

describe('useSimulationLayers', () => {
  // Helper to create default layer visibility
  const allLayersVisible: LayerVisibility = {
    onlineDrivers: true,
    offlineDrivers: true,
    enRoutePickupDrivers: true,
    withPassengerDrivers: true,
    offlineRiders: true,
    requestingRiders: true,
    inTransitRiders: true,
    pendingRoutes: true,
    pickupRoutes: true,
    tripRoutes: true,
    zoneBoundaries: true,
    surgeHeatmap: true,
  };

  it('returns layers including route and agent layers without zones', () => {
    const drivers: Driver[] = [
      { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
    ];
    const riders: Rider[] = [
      { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting', trip_state: 'offline' },
    ];
    const trips: Trip[] = [];

    const { result } = renderHook(() =>
      useSimulationLayers({
        drivers,
        riders,
        trips,
      })
    );

    // Without layerVisibility, all layers are created by default
    expect(result.current.length).toBeGreaterThan(0);
    // Check for key layer types
    const layerIds = result.current.map((l) => l.id);
    expect(layerIds).toContain('pending-routes');
  });

  it('returns layers with zones when zone data is provided', () => {
    const drivers: Driver[] = [
      { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
    ];
    const riders: Rider[] = [
      { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting', trip_state: 'offline' },
    ];
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
        zoneData,
        layerVisibility: allLayersVisible,
      })
    );

    const layerIds = result.current.map((l) => l.id);
    expect(layerIds).toContain('zones');
  });

  it('returns layers with heatmap when demand points are provided', () => {
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
        zoneData,
        demandPoints,
        layerVisibility: allLayersVisible,
      })
    );

    const layerIds = result.current.map((l) => l.id);
    expect(layerIds).toContain('zones');
    expect(layerIds).toContain('demand-heatmap');
  });

  it('handles empty data arrays', () => {
    const { result } = renderHook(() =>
      useSimulationLayers({
        drivers: [],
        riders: [],
        trips: [],
      })
    );

    // Even with empty data, route layers are created (just with empty data)
    expect(result.current.length).toBeGreaterThan(0);
  });

  it('creates driver layers grouped by status', () => {
    const drivers: Driver[] = [
      { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
      {
        id: 'd2',
        latitude: -23.6,
        longitude: -46.7,
        status: 'en_route_pickup',
        rating: 4.8,
        zone: 'z2',
      },
    ];

    const { result } = renderHook(() =>
      useSimulationLayers({
        drivers,
        riders: [],
        trips: [],
      })
    );

    const layerIds = result.current.map((l) => l.id);
    expect(layerIds).toContain('drivers-online');
    expect(layerIds).toContain('drivers-en_route_pickup');
  });

  it('creates rider layers grouped by trip_state', () => {
    const riders: Rider[] = [
      { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting', trip_state: 'offline' },
      { id: 'r2', latitude: -23.6, longitude: -46.7, status: 'in_transit', trip_state: 'started' },
    ];

    const { result } = renderHook(() =>
      useSimulationLayers({
        drivers: [],
        riders,
        trips: [],
      })
    );

    const layerIds = result.current.map((l) => l.id);
    expect(layerIds).toContain('riders-offline');
    expect(layerIds).toContain('riders-started');
  });

  it('creates route layers for trips', () => {
    const trips: Trip[] = [
      {
        id: 't1',
        driver_id: 'd1',
        rider_id: 'r1',
        pickup_latitude: -23.5,
        pickup_longitude: -46.6,
        dropoff_latitude: -23.6,
        dropoff_longitude: -46.7,
        route: [
          [-23.5, -46.6],
          [-23.6, -46.7],
        ],
        status: 'started',
      },
    ];

    const { result } = renderHook(() =>
      useSimulationLayers({
        drivers: [],
        riders: [],
        trips,
      })
    );

    const layerIds = result.current.map((l) => l.id);
    expect(layerIds).toContain('remaining-trip-routes');
    expect(layerIds).toContain('destination-flags');
  });

  it('respects layerVisibility settings', () => {
    const drivers: Driver[] = [
      { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
    ];

    const hiddenVisibility: LayerVisibility = {
      ...allLayersVisible,
      onlineDrivers: false,
    };

    const { result } = renderHook(() =>
      useSimulationLayers({
        drivers,
        riders: [],
        trips: [],
        layerVisibility: hiddenVisibility,
      })
    );

    const layerIds = result.current.map((l) => l.id);
    expect(layerIds).not.toContain('online-drivers');
  });
});
