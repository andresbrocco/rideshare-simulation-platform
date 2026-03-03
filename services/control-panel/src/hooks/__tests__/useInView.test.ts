import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, cleanup } from '@testing-library/react';
import { useInView } from '../useInView';
import type { UseInViewOptions } from '../useInView';

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

function TestComponent(props: { options?: UseInViewOptions }) {
  const [ref, isInView] = useInView<HTMLDivElement>(props.options);
  return React.createElement('div', {
    ref,
    'data-testid': 'observed',
    'data-inview': String(isInView),
  });
}

describe('useInView', () => {
  beforeEach(() => {
    intersectionCallback = null;
    mockDisconnect = vi.fn();
    mockObserve = vi.fn();
    vi.stubGlobal('IntersectionObserver', createMockIntersectionObserver());
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('isInView starts as false', () => {
    render(React.createElement(TestComponent));

    expect(screen.getByTestId('observed').dataset.inview).toBe('false');
  });

  it('isInView becomes true when element intersects', () => {
    render(React.createElement(TestComponent));

    act(() => {
      intersectionCallback?.([{ isIntersecting: true, intersectionRatio: 1 }]);
    });

    expect(screen.getByTestId('observed').dataset.inview).toBe('true');
  });

  it('triggerOnce disconnects observer after first intersection', () => {
    render(
      React.createElement(TestComponent, {
        options: { triggerOnce: true },
      })
    );

    // Before intersection, isInView is false
    expect(screen.getByTestId('observed').dataset.inview).toBe('false');

    act(() => {
      intersectionCallback?.([{ isIntersecting: true, intersectionRatio: 1 }]);
    });

    // After first intersection, isInView is true and observer is disconnected
    expect(screen.getByTestId('observed').dataset.inview).toBe('true');
    expect(mockDisconnect).toHaveBeenCalledTimes(1);
  });

  it('observer is disconnected on unmount', () => {
    const { unmount } = render(React.createElement(TestComponent));

    unmount();

    expect(mockDisconnect).toHaveBeenCalled();
  });
});
