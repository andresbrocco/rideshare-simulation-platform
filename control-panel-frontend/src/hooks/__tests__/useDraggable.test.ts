import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDraggable } from '../useDraggable';

describe('useDraggable', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns initial position', () => {
    const { result } = renderHook(() => useDraggable({ initialX: 100, initialY: 200 }));

    expect(result.current.position).toEqual({ x: 100, y: 200 });
  });

  it('starts with isDragging false', () => {
    const { result } = renderHook(() => useDraggable({ initialX: 100, initialY: 200 }));

    expect(result.current.isDragging).toBe(false);
  });

  it('sets isDragging true on handleMouseDown', () => {
    const { result } = renderHook(() => useDraggable({ initialX: 100, initialY: 200 }));

    const mockEvent = {
      clientX: 110,
      clientY: 210,
      preventDefault: vi.fn(),
    } as unknown as React.MouseEvent;

    act(() => {
      result.current.handleMouseDown(mockEvent);
    });

    expect(result.current.isDragging).toBe(true);
    expect(mockEvent.preventDefault).toHaveBeenCalled();
  });

  it('updates position on mouse move while dragging', () => {
    const { result } = renderHook(() => useDraggable({ initialX: 100, initialY: 200 }));

    // Start dragging
    const mouseDownEvent = {
      clientX: 110,
      clientY: 210,
      preventDefault: vi.fn(),
    } as unknown as React.MouseEvent;

    act(() => {
      result.current.handleMouseDown(mouseDownEvent);
    });

    // Simulate mouse move
    act(() => {
      const mouseMoveEvent = new MouseEvent('mousemove', {
        clientX: 150,
        clientY: 250,
      });
      document.dispatchEvent(mouseMoveEvent);
    });

    // Position should have changed based on delta (150-110=40, 250-210=40)
    expect(result.current.position.x).toBe(140); // 100 + 40
    expect(result.current.position.y).toBe(240); // 200 + 40
  });

  it('resets isDragging on handleMouseUp', () => {
    const { result } = renderHook(() => useDraggable({ initialX: 100, initialY: 200 }));

    // Start dragging
    const mockEvent = {
      clientX: 110,
      clientY: 210,
      preventDefault: vi.fn(),
    } as unknown as React.MouseEvent;

    act(() => {
      result.current.handleMouseDown(mockEvent);
    });

    expect(result.current.isDragging).toBe(true);

    // Stop dragging
    act(() => {
      const mouseUpEvent = new MouseEvent('mouseup');
      document.dispatchEvent(mouseUpEvent);
    });

    expect(result.current.isDragging).toBe(false);
  });

  it('clamps position to viewport bounds', () => {
    // Mock window dimensions
    Object.defineProperty(window, 'innerWidth', { value: 1024, writable: true });
    Object.defineProperty(window, 'innerHeight', { value: 768, writable: true });

    const { result } = renderHook(() =>
      useDraggable({ initialX: 900, initialY: 600, popupWidth: 320, popupHeight: 400 })
    );

    // Start dragging
    const mouseDownEvent = {
      clientX: 910,
      clientY: 610,
      preventDefault: vi.fn(),
    } as unknown as React.MouseEvent;

    act(() => {
      result.current.handleMouseDown(mouseDownEvent);
    });

    // Try to move beyond right/bottom bounds
    act(() => {
      const mouseMoveEvent = new MouseEvent('mousemove', {
        clientX: 1100,
        clientY: 900,
      });
      document.dispatchEvent(mouseMoveEvent);
    });

    // Position should be clamped
    expect(result.current.position.x).toBeLessThanOrEqual(1024 - 320);
    expect(result.current.position.y).toBeLessThanOrEqual(768 - 100);
  });

  it('updates position when initial coordinates change', () => {
    const { result, rerender } = renderHook(
      ({ initialX, initialY }) => useDraggable({ initialX, initialY }),
      { initialProps: { initialX: 100, initialY: 200 } }
    );

    expect(result.current.position).toEqual({ x: 100, y: 200 });

    rerender({ initialX: 300, initialY: 400 });

    expect(result.current.position).toEqual({ x: 300, y: 400 });
  });
});
