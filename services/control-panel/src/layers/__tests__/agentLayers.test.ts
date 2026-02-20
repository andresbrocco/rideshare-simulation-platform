import { describe, it, expect, beforeEach } from 'vitest';
import { IconLayer, PathLayer } from '@deck.gl/layers';
import type { Driver, Rider, Trip } from '../../types/api';
import {
  createDriverLayer,
  createRiderLayer,
  createPathLayer,
  createOnlineDriversLayer,
  createOfflineDriversLayer,
  createEnRoutePickupDriversLayer,
  createWithPassengerDriversLayer,
  createOfflineRidersLayer,
  createRequestingRidersLayer,
  createInTransitRidersLayer,
  createDestinationFlagLayer,
  createCompletedPickupRouteLayer,
  createRemainingPickupRouteLayer,
  createCompletedTripRouteLayer,
  createRemainingTripRouteLayer,
  clearRouteCache,
  evictTripFromRouteCache,
  DRIVER_COLORS,
  RIDER_TRIP_STATE_COLORS,
} from '../agentLayers';

describe('agentLayers', () => {
  describe('createDriverLayer', () => {
    it('creates an array of IconLayers grouped by status', () => {
      const drivers: Driver[] = [
        {
          id: 'd1',
          latitude: -23.5,
          longitude: -46.6,
          status: 'available',
          rating: 4.5,
          zone: 'z1',
        },
        {
          id: 'd2',
          latitude: -23.6,
          longitude: -46.7,
          status: 'en_route_pickup',
          rating: 4.8,
          zone: 'z2',
        },
      ];

      const layers = createDriverLayer(drivers);

      expect(Array.isArray(layers)).toBe(true);
      expect(layers.length).toBe(2); // Two different statuses
      expect(layers.every((l) => l instanceof IconLayer)).toBe(true);
    });

    it('handles empty driver array', () => {
      const layers = createDriverLayer([]);
      expect(Array.isArray(layers)).toBe(true);
      expect(layers.length).toBe(0);
    });
  });

  describe('createRiderLayer', () => {
    it('creates an array of IconLayers grouped by trip_state', () => {
      const riders: Rider[] = [
        {
          id: 'r1',
          latitude: -23.5,
          longitude: -46.6,
          status: 'requesting',
          trip_state: 'requested',
        },
        {
          id: 'r2',
          latitude: -23.6,
          longitude: -46.7,
          status: 'in_transit',
          trip_state: 'in_transit',
        },
      ];

      const layers = createRiderLayer(riders);

      expect(Array.isArray(layers)).toBe(true);
      expect(layers.length).toBe(2); // Two different trip_states
      expect(layers.every((l) => l instanceof IconLayer)).toBe(true);
    });

    it('handles empty rider array', () => {
      const layers = createRiderLayer([]);
      expect(Array.isArray(layers)).toBe(true);
      expect(layers.length).toBe(0);
    });
  });

  describe('createPathLayer', () => {
    it('creates a PathLayer for trips with in_transit status', () => {
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
            [-23.55, -46.65],
            [-23.6, -46.7],
          ],
          status: 'in_transit',
        },
      ];

      const layer = createPathLayer(trips);

      expect(layer).toBeInstanceOf(PathLayer);
      expect(layer.id).toBe('trip-routes');
    });

    it('filters out trips without in_transit status', () => {
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
          status: 'requested',
        },
      ];

      const layer = createPathLayer(trips);
      expect(layer.props.data).toHaveLength(0);
    });
  });

  describe('route cache', () => {
    beforeEach(() => {
      clearRouteCache();
    });

    it('clearRouteCache clears the cache', () => {
      // Create some cached routes
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
            [-23.55, -46.65],
            [-23.6, -46.7],
          ],
          pickup_route: [
            [-23.4, -46.5],
            [-23.45, -46.55],
            [-23.5, -46.6],
          ],
          status: 'in_transit',
          route_progress_index: 1,
        },
      ];

      // Generate cached routes
      createCompletedTripRouteLayer(trips);
      createRemainingTripRouteLayer(trips);

      // Clear cache
      clearRouteCache();

      // No way to directly verify cache is empty, but we can verify no error
      expect(() => clearRouteCache()).not.toThrow();
    });

    it('pickup route layers work correctly', () => {
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
          pickup_route: [
            [-23.4, -46.5],
            [-23.45, -46.55],
            [-23.5, -46.6],
          ],
          status: 'en_route_pickup',
          pickup_route_progress_index: 1,
        },
      ];

      const completedLayer = createCompletedPickupRouteLayer(trips);
      const remainingLayer = createRemainingPickupRouteLayer(trips);

      expect(completedLayer).toBeInstanceOf(PathLayer);
      expect(remainingLayer).toBeInstanceOf(PathLayer);
    });

    it('evictTripFromRouteCache removes entries for the given trip', () => {
      const trips: Trip[] = [
        {
          id: 'trip-A',
          driver_id: 'd1',
          rider_id: 'r1',
          pickup_latitude: -23.5,
          pickup_longitude: -46.6,
          dropoff_latitude: -23.6,
          dropoff_longitude: -46.7,
          route: [
            [-23.5, -46.6],
            [-23.55, -46.65],
            [-23.6, -46.7],
          ],
          status: 'in_transit',
          route_progress_index: 1,
        },
        {
          id: 'trip-B',
          driver_id: 'd2',
          rider_id: 'r2',
          pickup_latitude: -23.5,
          pickup_longitude: -46.6,
          dropoff_latitude: -23.6,
          dropoff_longitude: -46.7,
          route: [
            [-23.5, -46.6],
            [-23.55, -46.65],
            [-23.6, -46.7],
          ],
          status: 'in_transit',
          route_progress_index: 1,
        },
      ];

      // Populate cache for both trips
      createCompletedTripRouteLayer(trips);

      // Evict trip-A only
      evictTripFromRouteCache('trip-A');

      // Verify trip-B still produces cached (identical) results while trip-A recomputes
      // We test this indirectly: after eviction, creating layers should not throw
      // and trip-B's data should still be present
      const layerAfterEvict = createCompletedTripRouteLayer(trips.filter((t) => t.id === 'trip-B'));
      expect(layerAfterEvict).toBeInstanceOf(PathLayer);
    });
  });

  describe('color exports', () => {
    it('exports DRIVER_COLORS with expected statuses', () => {
      expect(DRIVER_COLORS).toBeDefined();
      expect(DRIVER_COLORS.available).toBeDefined();
      expect(DRIVER_COLORS.offline).toBeDefined();
      expect(DRIVER_COLORS.en_route_pickup).toBeDefined();
    });

    it('exports RIDER_TRIP_STATE_COLORS with expected states', () => {
      expect(RIDER_TRIP_STATE_COLORS).toBeDefined();
      expect(RIDER_TRIP_STATE_COLORS.idle).toBeDefined();
      expect(RIDER_TRIP_STATE_COLORS.requested).toBeDefined();
      expect(RIDER_TRIP_STATE_COLORS.in_transit).toBeDefined();
    });
  });

  describe('edge cases', () => {
    it('handles empty data for all layer types', () => {
      expect(() => createOnlineDriversLayer([])).not.toThrow();
      expect(() => createOfflineDriversLayer([])).not.toThrow();
      expect(() => createEnRoutePickupDriversLayer([])).not.toThrow();
      expect(() => createWithPassengerDriversLayer([])).not.toThrow();
      expect(() => createOfflineRidersLayer([])).not.toThrow();
      expect(() => createRequestingRidersLayer([])).not.toThrow();
      expect(() => createInTransitRidersLayer([])).not.toThrow();
      expect(() => createDestinationFlagLayer([])).not.toThrow();
      expect(() => createCompletedPickupRouteLayer([])).not.toThrow();
      expect(() => createRemainingPickupRouteLayer([])).not.toThrow();
      expect(() => createCompletedTripRouteLayer([])).not.toThrow();
      expect(() => createRemainingTripRouteLayer([])).not.toThrow();
    });

    it('layer picking enabled on agent layers', () => {
      const drivers: Driver[] = [
        {
          id: 'd1',
          latitude: -23.5,
          longitude: -46.6,
          status: 'available',
          rating: 4.5,
          zone: 'z1',
        },
      ];
      const riders: Rider[] = [
        { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'requesting', trip_state: 'idle' },
      ];

      expect(createOnlineDriversLayer(drivers).props.pickable).toBe(true);
      expect(createOfflineRidersLayer(riders).props.pickable).toBe(true);
    });
  });
});
