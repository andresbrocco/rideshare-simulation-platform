import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useActiveSection } from '../useActiveSection';

type IntersectionCallback = (entries: Partial<IntersectionObserverEntry>[]) => void;

let intersectionCallback: IntersectionCallback | null = null;
let mockDisconnect: ReturnType<typeof vi.fn>;
let mockObserve: ReturnType<typeof vi.fn>;

function createMockIntersectionObserver() {
  return vi.fn().mockImplementation((callback: IntersectionCallback) => {
    intersectionCallback = callback;
    return {
      observe: mockObserve,
      unobserve: vi.fn(),
      disconnect: mockDisconnect,
    };
  });
}

const SECTION_IDS = ['hero', 'architecture', 'tech-stack'] as const;

describe('useActiveSection', () => {
  beforeEach(() => {
    intersectionCallback = null;
    mockDisconnect = vi.fn();
    mockObserve = vi.fn();
    vi.stubGlobal('IntersectionObserver', createMockIntersectionObserver());

    for (const id of SECTION_IDS) {
      const el = document.createElement('section');
      el.id = id;
      document.body.appendChild(el);
    }
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    for (const id of SECTION_IDS) {
      const el = document.getElementById(id);
      if (el) el.remove();
    }
  });

  it('returns null initially', () => {
    const { result } = renderHook(() => useActiveSection(SECTION_IDS));

    expect(result.current).toBeNull();
  });

  it('returns the id of the section with the highest intersectionRatio', () => {
    const { result } = renderHook(() => useActiveSection(SECTION_IDS));

    act(() => {
      const heroEl = document.getElementById('hero');
      const archEl = document.getElementById('architecture');
      const techEl = document.getElementById('tech-stack');

      intersectionCallback?.([
        {
          target: heroEl as Element,
          intersectionRatio: 0.1,
          isIntersecting: true,
        },
        {
          target: archEl as Element,
          intersectionRatio: 0.7,
          isIntersecting: true,
        },
        {
          target: techEl as Element,
          intersectionRatio: 0.3,
          isIntersecting: true,
        },
      ]);
    });

    expect(result.current).toBe('architecture');
  });

  it('updates when ratios change', () => {
    const { result } = renderHook(() => useActiveSection(SECTION_IDS));

    const archEl = document.getElementById('architecture');
    const techEl = document.getElementById('tech-stack');

    act(() => {
      intersectionCallback?.([
        {
          target: archEl as Element,
          intersectionRatio: 0.7,
          isIntersecting: true,
        },
      ]);
    });

    expect(result.current).toBe('architecture');

    act(() => {
      intersectionCallback?.([
        {
          target: techEl as Element,
          intersectionRatio: 0.9,
          isIntersecting: true,
        },
      ]);
    });

    expect(result.current).toBe('tech-stack');
  });

  it('observer is disconnected on unmount', () => {
    const { unmount } = renderHook(() => useActiveSection(SECTION_IDS));

    unmount();

    expect(mockDisconnect).toHaveBeenCalled();
  });
});
