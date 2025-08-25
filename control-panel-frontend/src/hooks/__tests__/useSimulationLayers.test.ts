import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useSimulationLayers } from '../useSimulationLayers';
import type { Driver, Rider, Trip } from '../../types/api';

describe('useSimulationLayers', () => {
  it('returns array of layers in correct order', () => {
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
