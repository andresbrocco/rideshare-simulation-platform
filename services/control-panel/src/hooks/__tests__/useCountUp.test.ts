import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCountUp } from '../useCountUp';

describe('useCountUp', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('returns 0 when start is false', () => {
    const { result } = renderHook(() => useCountUp({ target: 100, start: false }));

    expect(result.current).toBe(0);
  });

  it('returns target immediately when prefers-reduced-motion is true', () => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: true,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    const { result } = renderHook(() => useCountUp({ target: 42, start: true }));

    expect(result.current).toBe(42);
  });

  it('animates from 0 to target over duration', () => {
    let rafCallback: ((timestamp: number) => void) | null = null;
    let rafId = 1;

    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
      rafCallback = cb;
      return rafId++;
    });

    const { result } = renderHook(() => useCountUp({ target: 100, duration: 1000, start: true }));

    expect(result.current).toBe(0);

    // Simulate halfway through the animation
    act(() => {
      rafCallback?.(0);
    });
    act(() => {
      rafCallback?.(500);
    });

    expect(result.current).toBeGreaterThan(0);
    expect(result.current).toBeLessThan(100);

    // Simulate completion
    act(() => {
      rafCallback?.(1000);
    });

    expect(result.current).toBe(100);
  });

  it('cancels animation on unmount', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame');

    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(() => 42);

    const { unmount } = renderHook(() => useCountUp({ target: 100, start: true }));

    unmount();

    expect(cancelSpy).toHaveBeenCalledWith(42);
  });
});
