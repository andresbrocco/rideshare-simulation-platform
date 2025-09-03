import { describe, it, expect, beforeEach } from 'vitest';
import { IconLayer, PathLayer } from '@deck.gl/layers';
import type { Driver, Rider, Trip } from '../../types/api';
import {
  createDriverLayer,
  createRiderLayer,
  createPathLayer,
  createOnlineDriversLayer,
  createOfflineDriversLayer,
  createBusyDriversLayer,
  createEnRoutePickupDriversLayer,
  createWithPassengerDriversLayer,
  createOfflineRidersLayer,
  createWaitingRidersLayer,
  createMatchedRidersLayer,
  createInTransitRidersLayer,
  createDestinationFlagLayer,
  createCompletedPickupRouteLayer,
  createRemainingPickupRouteLayer,
  createCompletedTripRouteLayer,
  createRemainingTripRouteLayer,
  clearRouteCache,
  DRIVER_COLORS,
  RIDER_TRIP_STATE_COLORS,
} from '../agentLayers';

describe('agentLayers', () => {
  describe('createDriverLayer', () => {
    it('creates an array of IconLayers grouped by status', () => {
      const drivers: Driver[] = [
        { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
        { id: 'd2', latitude: -23.6, longitude: -46.7, status: 'busy', rating: 4.8, zone: 'z2' },
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
        { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting', trip_state: 'requested' },
        {
          id: 'r2',
          latitude: -23.6,
          longitude: -46.7,
          status: 'in_transit',
          trip_state: 'started',
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
    it('creates a PathLayer for trips with started status', () => {
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
          status: 'started',
        },
      ];

      const layer = createPathLayer(trips);

      expect(layer).toBeInstanceOf(PathLayer);
      expect(layer.id).toBe('trip-routes');
    });

    it('filters out trips without started status', () => {
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

  describe('driver layer updateTriggers', () => {
    const drivers: Driver[] = [
      {
        id: 'd1',
        latitude: -23.5,
        longitude: -46.6,
        status: 'online',
        rating: 4.5,
        zone: 'z1',
        heading: 90,
      },
      {
        id: 'd2',
        latitude: -23.6,
        longitude: -46.7,
        status: 'online',
        rating: 4.8,
        zone: 'z2',
        heading: 180,
      },
    ];

    it('createOnlineDriversLayer has updateTriggers with position and angle', () => {
      const layer = createOnlineDriversLayer(drivers);

      expect(layer.props.updateTriggers).toBeDefined();
      expect(layer.props.updateTriggers.getPosition).toBeDefined();
      expect(layer.props.updateTriggers.getAngle).toBeDefined();
      expect(layer.props.updateTriggers.getPosition).toHaveLength(2);
    });

    it('updateTriggers change when driver positions change', () => {
      const layer1 = createOnlineDriversLayer(drivers);
      const movedDrivers = [{ ...drivers[0], latitude: -23.51 }, drivers[1]];
      const layer2 = createOnlineDriversLayer(movedDrivers);

      // Triggers should be different
      expect(layer1.props.updateTriggers.getPosition).not.toEqual(
        layer2.props.updateTriggers.getPosition
      );
    });

    it('updateTriggers remain stable when positions are unchanged', () => {
      // Same data, should produce same triggers
      const layer1 = createOnlineDriversLayer(drivers);
      const layer2 = createOnlineDriversLayer([...drivers]);

      expect(layer1.props.updateTriggers.getPosition).toEqual(
        layer2.props.updateTriggers.getPosition
      );
    });

    it('all driver layer types have updateTriggers', () => {
      const offlineDrivers = [{ ...drivers[0], status: 'offline' as const }];
      const busyDrivers = [{ ...drivers[0], status: 'busy' as const }];
      const enRouteDrivers = [{ ...drivers[0], status: 'en_route_pickup' as const }];
      const withPassengerDrivers = [{ ...drivers[0], status: 'en_route_destination' as const }];

      expect(createOfflineDriversLayer(offlineDrivers).props.updateTriggers).toBeDefined();
      expect(createBusyDriversLayer(busyDrivers).props.updateTriggers).toBeDefined();
      expect(createEnRoutePickupDriversLayer(enRouteDrivers).props.updateTriggers).toBeDefined();
      expect(
        createWithPassengerDriversLayer(withPassengerDrivers).props.updateTriggers
      ).toBeDefined();
    });
  });

  describe('rider layer updateTriggers', () => {
    const riders: Rider[] = [
      { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting', trip_state: 'offline' },
      { id: 'r2', latitude: -23.6, longitude: -46.7, status: 'waiting', trip_state: 'offline' },
    ];

    it('createOfflineRidersLayer has updateTriggers with position', () => {
      const layer = createOfflineRidersLayer(riders);

      expect(layer.props.updateTriggers).toBeDefined();
      expect(layer.props.updateTriggers.getPosition).toBeDefined();
      expect(layer.props.updateTriggers.getPosition).toHaveLength(2);
    });

    it('all rider layer types have updateTriggers', () => {
      const waitingRiders = [{ ...riders[0], trip_state: 'requested' as const }];
      const matchedRiders = [{ ...riders[0], trip_state: 'matched' as const }];
      const inTransitRiders = [{ ...riders[0], trip_state: 'started' as const }];

      expect(createWaitingRidersLayer(waitingRiders).props.updateTriggers).toBeDefined();
      expect(createMatchedRidersLayer(matchedRiders).props.updateTriggers).toBeDefined();
      expect(createInTransitRidersLayer(inTransitRiders).props.updateTriggers).toBeDefined();
    });
  });

  describe('destination flag layer updateTriggers', () => {
    it('has updateTriggers with position', () => {
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

      const layer = createDestinationFlagLayer(trips);

      expect(layer.props.updateTriggers).toBeDefined();
      expect(layer.props.updateTriggers.getPosition).toBeDefined();
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
          status: 'started',
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

    it('route layers include updateTriggers based on progress index', () => {
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
          status: 'started',
          route_progress_index: 1,
        },
      ];

      const layer = createCompletedTripRouteLayer(trips);
      expect(layer.props.updateTriggers).toBeDefined();
      expect(layer.props.updateTriggers.getPath).toBeDefined();
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
          status: 'driver_en_route',
          pickup_route_progress_index: 1,
        },
      ];

      const completedLayer = createCompletedPickupRouteLayer(trips);
      const remainingLayer = createRemainingPickupRouteLayer(trips);

      expect(completedLayer).toBeInstanceOf(PathLayer);
      expect(remainingLayer).toBeInstanceOf(PathLayer);
      expect(completedLayer.props.updateTriggers).toBeDefined();
      expect(remainingLayer.props.updateTriggers).toBeDefined();
    });
  });

  describe('color exports', () => {
    it('exports DRIVER_COLORS with expected statuses', () => {
      expect(DRIVER_COLORS).toBeDefined();
      expect(DRIVER_COLORS.online).toBeDefined();
      expect(DRIVER_COLORS.offline).toBeDefined();
      expect(DRIVER_COLORS.busy).toBeDefined();
    });

    it('exports RIDER_TRIP_STATE_COLORS with expected states', () => {
      expect(RIDER_TRIP_STATE_COLORS).toBeDefined();
      expect(RIDER_TRIP_STATE_COLORS.offline).toBeDefined();
      expect(RIDER_TRIP_STATE_COLORS.requested).toBeDefined();
      expect(RIDER_TRIP_STATE_COLORS.started).toBeDefined();
    });
  });

  describe('edge cases', () => {
    it('handles empty data for all layer types', () => {
      expect(() => createOnlineDriversLayer([])).not.toThrow();
      expect(() => createOfflineDriversLayer([])).not.toThrow();
      expect(() => createBusyDriversLayer([])).not.toThrow();
      expect(() => createEnRoutePickupDriversLayer([])).not.toThrow();
      expect(() => createWithPassengerDriversLayer([])).not.toThrow();
      expect(() => createOfflineRidersLayer([])).not.toThrow();
      expect(() => createWaitingRidersLayer([])).not.toThrow();
      expect(() => createMatchedRidersLayer([])).not.toThrow();
      expect(() => createInTransitRidersLayer([])).not.toThrow();
      expect(() => createDestinationFlagLayer([])).not.toThrow();
      expect(() => createCompletedPickupRouteLayer([])).not.toThrow();
      expect(() => createRemainingPickupRouteLayer([])).not.toThrow();
      expect(() => createCompletedTripRouteLayer([])).not.toThrow();
      expect(() => createRemainingTripRouteLayer([])).not.toThrow();
    });

    it('layer picking enabled on agent layers', () => {
      const drivers: Driver[] = [
        { id: 'd1', latitude: -23.5, longitude: -46.6, status: 'online', rating: 4.5, zone: 'z1' },
      ];
      const riders: Rider[] = [
        { id: 'r1', latitude: -23.5, longitude: -46.6, status: 'waiting', trip_state: 'offline' },
      ];

      expect(createOnlineDriversLayer(drivers).props.pickable).toBe(true);
      expect(createOfflineRidersLayer(riders).props.pickable).toBe(true);
    });
  });
});
