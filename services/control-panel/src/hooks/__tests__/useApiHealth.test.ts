import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useApiHealth } from '../useApiHealth';

describe('useApiHealth', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('returns available: true when health check succeeds', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 200,
    });

    const { result } = renderHook(() => useApiHealth('http://localhost:8000'));

    expect(result.current.checking).toBe(true);

    await waitFor(() => {
      expect(result.current.available).toBe(true);
      expect(result.current.checking).toBe(false);
      expect(result.current.error).toBeNull();
      expect(result.current.lastChecked).toBeInstanceOf(Date);
    });
  });

  it('returns available: false when fetch throws network error', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useApiHealth('http://localhost:8000'));

    await waitFor(() => {
      expect(result.current.available).toBe(false);
      expect(result.current.checking).toBe(false);
      expect(result.current.error).toBe('Network error');
    });
  });

  it('returns available: false when server returns non-ok status', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false,
      status: 503,
    });

    const { result } = renderHook(() => useApiHealth('http://localhost:8000'));

    await waitFor(() => {
      expect(result.current.available).toBe(false);
      expect(result.current.checking).toBe(false);
      expect(result.current.error).toBe('HTTP 503');
    });
  });

  it('handles timeout after 5 seconds via AbortController', async () => {
    let capturedSignal: AbortSignal | undefined;

    (global.fetch as ReturnType<typeof vi.fn>).mockImplementation(
      (_url: string, init?: RequestInit) => {
        capturedSignal = init?.signal;
        // Simulate a slow fetch that rejects when aborted
        return new Promise((_resolve, reject) => {
          if (capturedSignal) {
            capturedSignal.addEventListener('abort', () => {
              reject(new DOMException('The operation was aborted.', 'AbortError'));
            });
          }
        });
      }
    );

    const { result } = renderHook(() => useApiHealth('http://localhost:8000'));

    expect(result.current.checking).toBe(true);

    // Advance past the 5s timeout to trigger AbortController
    vi.advanceTimersByTime(5001);

    await waitFor(() => {
      expect(result.current.available).toBe(false);
      expect(result.current.checking).toBe(false);
      expect(result.current.error).toContain('aborted');
    });

    expect(capturedSignal?.aborted).toBe(true);
  }, 10000);

  it('polls at the specified interval', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 200,
    });

    renderHook(() => useApiHealth('http://localhost:8000', 10000));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      vi.advanceTimersByTime(10000);
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });
  });

  it('transitions from unavailable to available on recovery', async () => {
    const fetchMock = global.fetch as ReturnType<typeof vi.fn>;
    fetchMock.mockRejectedValueOnce(new Error('Network error'));

    const { result } = renderHook(() => useApiHealth('http://localhost:8000', 10000));

    await waitFor(() => {
      expect(result.current.available).toBe(false);
    });

    fetchMock.mockResolvedValueOnce({ ok: true, status: 200 });

    await act(async () => {
      vi.advanceTimersByTime(10000);
    });

    await waitFor(() => {
      expect(result.current.available).toBe(true);
      expect(result.current.error).toBeNull();
    });
  });

  it('fetches the /health endpoint with the provided API URL', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 200,
    });

    renderHook(() => useApiHealth('https://api.example.com'));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.example.com/health',
        expect.objectContaining({ method: 'GET', signal: expect.anything() })
      );
    });
  });

  it('cleans up interval on unmount', async () => {
    (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      status: 200,
    });

    const { unmount } = renderHook(() => useApiHealth('http://localhost:8000', 10000));

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    unmount();

    await act(async () => {
      vi.advanceTimersByTime(10000);
    });

    // No additional calls after unmount
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
});
