import { describe, it, expect } from 'vitest';
import { formatTripState } from '../tripStateFormatter';

describe('formatTripState', () => {
  it('formats idle state', () => {
    expect(formatTripState('idle')).toBe('Idle');
  });

  it('formats requested state', () => {
    expect(formatTripState('requested')).toBe('Requesting ride');
  });

  it('formats offer_sent state', () => {
    expect(formatTripState('offer_sent')).toBe('Finding driver');
  });

  it('formats offer_expired state', () => {
    expect(formatTripState('offer_expired')).toBe('Finding another driver');
  });

  it('formats offer_rejected state', () => {
    expect(formatTripState('offer_rejected')).toBe('Finding another driver');
  });

  it('formats driver_assigned state', () => {
    expect(formatTripState('driver_assigned')).toBe('Driver assigned');
  });

  it('formats en_route_pickup state', () => {
    expect(formatTripState('en_route_pickup')).toBe('Waiting for pickup');
  });

  it('formats at_pickup state', () => {
    expect(formatTripState('at_pickup')).toBe('Driver at pickup');
  });

  it('formats in_transit state', () => {
    expect(formatTripState('in_transit')).toBe('In transit');
  });

  it('formats completed state', () => {
    expect(formatTripState('completed')).toBe('Completed');
  });

  it('formats cancelled state', () => {
    expect(formatTripState('cancelled')).toBe('Cancelled');
  });
});
