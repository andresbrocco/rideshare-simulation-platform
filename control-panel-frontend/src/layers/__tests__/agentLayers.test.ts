import { describe, it, expect } from 'vitest';
import { ScatterplotLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import { PathLayer } from '@deck.gl/layers';
import type { Driver, Rider, Trip, GPSTrail } from '../../types/api';
import {
  createDriverLayer,
  createRiderLayer,
  createTripsLayer,
  createPathLayer,
  DRIVER_COLORS,
  RIDER_COLORS,
} from '../agentLayers';

describe('agentLayers', () => {
  describe('createDriverLayer', () => {
    it('test_create_driver_layer', () => {
      const drivers: Driver[] = [
        { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
        { id: 'd2', latitude: -23.6, longitude: -46.7, status: 'busy', rating: 4.8, zone: 'z2' },
      ];

      const layer = createDriverLayer(drivers);

      expect(layer).toBeInstanceOf(ScatterplotLayer);
      expect(layer.id).toBe('drivers');
      expect(layer.props.data).toBe(drivers);
    });

    it('test_driver_color_by_status', () => {
      const drivers: Driver[] = [
        { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
        { id: 'd2', latitude: -23.6, longitude: -46.7, status: 'busy', rating: 4.8, zone: 'z2' },
        { id: 'd3', latitude: -23.7, longitude: -46.8, status: 'offline', rating: 4.2, zone: 'z3' },
        {
          id: 'd4',
          latitude: -23.8,
          longitude: -46.9,
          status: 'en_route',
          rating: 4.6,
          zone: 'z4',
        },
      ];

      const layer = createDriverLayer(drivers);
      const getFillColor = layer.props.getFillColor as (d: Driver) => number[];

      expect(getFillColor(drivers[0])).toEqual(DRIVER_COLORS.online);
      expect(getFillColor(drivers[1])).toEqual(DRIVER_COLORS.busy);
      expect(getFillColor(drivers[2])).toEqual(DRIVER_COLORS.offline);
      expect(getFillColor(drivers[3])).toEqual(DRIVER_COLORS.en_route);
    });

    it('test_driver_layer_radius', () => {
      const drivers: Driver[] = [
        { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
      ];

      const layer = createDriverLayer(drivers);

      expect(layer.props.getRadius).toBe(50);
    });
  });

  describe('createRiderLayer', () => {
    it('test_create_rider_layer', () => {
      const riders: Rider[] = [
        { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting' },
        { id: 'r2', latitude: -23.6, longitude: -46.7, status: 'in_transit' },
      ];

      const layer = createRiderLayer(riders);

      expect(layer).toBeInstanceOf(ScatterplotLayer);
      expect(layer.id).toBe('riders');
      expect(layer.props.data).toBe(riders);
    });

    it('test_rider_color_by_status', () => {
      const riders: Rider[] = [
        { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting' },
        { id: 'r2', latitude: -23.6, longitude: -46.7, status: 'in_transit' },
      ];

      const layer = createRiderLayer(riders);
      const getFillColor = layer.props.getFillColor as (d: Rider) => number[];

      expect(getFillColor(riders[0])).toEqual(RIDER_COLORS.waiting);
      expect(getFillColor(riders[1])).toEqual(RIDER_COLORS.in_transit);
    });
  });

  describe('createTripsLayer', () => {
    it('test_create_trips_layer', () => {
      const trails: GPSTrail[] = [
        {
          id: 't1',
          path: [
            [-46.6, -23.5, 100],
            [-46.61, -23.51, 200],
          ],
        },
      ];

      const layer = createTripsLayer(trails, 200);

      expect(layer).toBeInstanceOf(TripsLayer);
      expect(layer.id).toBe('gps-trails');
      expect(layer.props.data).toBe(trails);
      expect(layer.props.currentTime).toBe(200);
    });

    it('test_trips_layer_fade_effect', () => {
      const trails: GPSTrail[] = [
        {
          id: 't1',
          path: [
            [-46.6, -23.5, 100],
            [-46.61, -23.51, 200],
          ],
        },
      ];

      const layer = createTripsLayer(trails, 200);

      expect(layer.props.trailLength).toBe(300);
    });
  });

  describe('createPathLayer', () => {
    it('test_create_path_layer', () => {
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
            [-46.6, -23.5],
            [-46.65, -23.55],
            [-46.7, -23.6],
          ],
          status: 'STARTED',
        },
      ];

      const layer = createPathLayer(trips);

      expect(layer).toBeInstanceOf(PathLayer);
      expect(layer.id).toBe('trip-routes');
      expect(layer.props.data).toBe(trips);
    });
  });

  describe('edge cases', () => {
    it('test_empty_data_handling', () => {
      const driverLayer = createDriverLayer([]);
      const riderLayer = createRiderLayer([]);
      const tripsLayer = createTripsLayer([], 0);
      const pathLayer = createPathLayer([]);

      expect(driverLayer).toBeInstanceOf(ScatterplotLayer);
      expect(riderLayer).toBeInstanceOf(ScatterplotLayer);
      expect(tripsLayer).toBeInstanceOf(TripsLayer);
      expect(pathLayer).toBeInstanceOf(PathLayer);
    });

    it('test_layer_picking_enabled', () => {
      const drivers: Driver[] = [
        { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
      ];
      const riders: Rider[] = [{ id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting' }];
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
            [-46.6, -23.5],
            [-46.7, -23.6],
          ],
          status: 'STARTED',
        },
      ];

      const driverLayer = createDriverLayer(drivers);
      const riderLayer = createRiderLayer(riders);
      const pathLayer = createPathLayer(trips);

      expect(driverLayer.props.pickable).toBe(true);
      expect(riderLayer.props.pickable).toBe(true);
      expect(pathLayer.props.pickable).toBe(true);
    });
  });
});
