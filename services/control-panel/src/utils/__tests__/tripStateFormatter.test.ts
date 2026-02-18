import { describe, it, expect } from 'vitest';
import { formatTripState } from '../tripStateFormatter';

describe('formatTripState', () => {
  it('formats requested state', () => {
    expect(formatTripState('requested')).toBe('Waiting for match');
  });

  it('formats offer_sent state', () => {
    expect(formatTripState('offer_sent')).toBe('Offer sent to driver');
  });

  it('formats offer_expired state', () => {
    expect(formatTripState('offer_expired')).toBe('Offer expired');
  });

  it('formats offer_rejected state', () => {
    expect(formatTripState('offer_rejected')).toBe('Offer rejected');
  });

  it('formats matched state', () => {
    expect(formatTripState('matched')).toBe('Driver assigned');
  });

  it('formats driver_en_route state', () => {
    expect(formatTripState('driver_en_route')).toBe('Driver en route');
  });

  it('formats driver_arrived state', () => {
    expect(formatTripState('driver_arrived')).toBe('Driver arrived');
  });

  it('formats started state', () => {
    expect(formatTripState('started')).toBe('In progress');
  });

  it('formats completed state', () => {
    expect(formatTripState('completed')).toBe('Completed');
  });

  it('formats cancelled state', () => {
    expect(formatTripState('cancelled')).toBe('Cancelled');
  });

  it('returns original state for unknown states', () => {
    expect(formatTripState('unknown_state')).toBe('unknown_state');
  });
});
