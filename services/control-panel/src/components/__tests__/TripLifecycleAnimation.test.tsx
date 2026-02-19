import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TripLifecycleAnimation } from '../TripLifecycleAnimation';
import { resolvePhase } from '../tripLifecyclePhases';

// Mock canvas-confetti
vi.mock('canvas-confetti', () => ({
  default: {
    create: () => vi.fn(),
  },
}));

function mockMatchMedia(reduceMotion: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(prefers-reduced-motion: reduce)' ? reduceMotion : false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
}

// jsdom doesn't implement SVG geometry methods.
// Patch before each test to ensure fresh mocks.
beforeEach(() => {
  // @ts-expect-error -- SVGElement doesn't declare getTotalLength, but jsdom <path> elements are SVGElement
  SVGElement.prototype.getTotalLength = vi.fn().mockReturnValue(900);
  // @ts-expect-error -- same as above
  SVGElement.prototype.getPointAtLength = vi.fn().mockReturnValue({ x: 100, y: 40 });
});

describe('TripLifecycleAnimation', () => {
  beforeEach(() => {
    mockMatchMedia(false);
  });

  it('renders SVG with role="img" and aria-label', () => {
    render(<TripLifecycleAnimation />);

    const svg = screen.getByRole('img');
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute(
      'aria-label',
      'Animated trip lifecycle: a driver picks up a rider and drives to the destination'
    );
  });

  it('renders three icon image elements', () => {
    const { container } = render(<TripLifecycleAnimation />);

    const images = container.querySelectorAll('image');
    expect(images).toHaveLength(3);

    const hrefs = Array.from(images).map((img) => img.getAttribute('href'));
    expect(hrefs).toContain('/icons/car.png');
    expect(hrefs).toContain('/icons/person.png');
    expect(hrefs).toContain('/icons/flag-checkered.png');
  });

  it('renders background road path', () => {
    const { container } = render(<TripLifecycleAnimation />);

    const paths = container.querySelectorAll('path');
    expect(paths.length).toBeGreaterThanOrEqual(1);
    const roadPath = paths[0];
    expect(roadPath).toHaveAttribute('d');
    expect(roadPath.getAttribute('stroke')).toBe('rgba(0,255,136,0.06)');
  });

  it('renders two SVG tint filters in defs', () => {
    const { container } = render(<TripLifecycleAnimation />);

    const filters = container.querySelectorAll('filter');
    expect(filters).toHaveLength(2);
    expect(filters[0]).toHaveAttribute('id', 'car-tint');
    expect(filters[1]).toHaveAttribute('id', 'person-tint');
  });

  it('calls requestAnimationFrame on mount', () => {
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(1);
    render(<TripLifecycleAnimation />);
    expect(rafSpy).toHaveBeenCalled();
    rafSpy.mockRestore();
  });

  it('calls cancelAnimationFrame on unmount', () => {
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame').mockReturnValue(42);
    const cafSpy = vi.spyOn(window, 'cancelAnimationFrame');

    const { unmount } = render(<TripLifecycleAnimation />);
    unmount();

    expect(cafSpy).toHaveBeenCalledWith(42);
    rafSpy.mockRestore();
    cafSpy.mockRestore();
  });

  it('respects prefers-reduced-motion: reduce (no rAF call)', () => {
    mockMatchMedia(true);
    const rafSpy = vi.spyOn(window, 'requestAnimationFrame');

    render(<TripLifecycleAnimation />);

    expect(rafSpy).not.toHaveBeenCalled();
    rafSpy.mockRestore();
  });
});

describe('resolvePhase', () => {
  it('returns idle at progress 0 for cycleTime 0', () => {
    const result = resolvePhase(0);
    expect(result.phase).toBe('idle');
    expect(result.progress).toBeCloseTo(0);
  });

  it('returns idle at midpoint for cycleTime 0.5', () => {
    const result = resolvePhase(0.5);
    expect(result.phase).toBe('idle');
    expect(result.progress).toBeCloseTo(0.5);
  });

  it('returns driver_online after idle duration', () => {
    const result = resolvePhase(1.0);
    expect(result.phase).toBe('driver_online');
    expect(result.progress).toBeCloseTo(0);
  });

  it('wraps around after total cycle duration', () => {
    // TOTAL_CYCLE_DURATION = 13.0
    const result = resolvePhase(13.0 + 0.5);
    const expected = resolvePhase(0.5);
    expect(result.phase).toBe(expected.phase);
    expect(result.progress).toBeCloseTo(expected.progress);
  });

  it('handles negative cycleTime by wrapping', () => {
    // -1.0 mod 13.0 → 12.0, which falls in the 'hold' phase (starts at 10.5, duration 2.0)
    const result = resolvePhase(-1.0);
    expect(result.phase).toBe('hold');
  });
});
