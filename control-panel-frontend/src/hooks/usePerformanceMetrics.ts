import { useState, useEffect, useCallback, useRef } from 'react';
import type { PerformanceMetrics, FrontendMetrics } from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const POLL_INTERVAL = 2000; // 2 seconds

interface UsePerformanceMetricsReturn {
  metrics: PerformanceMetrics | null;
  frontendMetrics: FrontendMetrics;
  loading: boolean;
  error: string | null;
  recordWsMessage: () => void;
  refresh: () => void;
}

export function usePerformanceMetrics(): UsePerformanceMetricsReturn {
  const pollInterval = POLL_INTERVAL;
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Frontend metrics tracking
  const [wsMessagesPerSec, setWsMessagesPerSec] = useState(0);
  const [renderFps, setRenderFps] = useState(60);

  // Message count tracking
  const wsMessageCount = useRef(0);
  const lastWsCountTime = useRef(Date.now());

  // FPS tracking
  const frameCount = useRef(0);
  const lastFpsTime = useRef(Date.now());

  // Abort controller ref for cleanup
  const abortControllerRef = useRef<AbortController | null>(null);

  // Fetch performance metrics from API
  const fetchMetrics = useCallback(async (signal?: AbortSignal) => {
    try {
      const apiKey = sessionStorage.getItem('apiKey') || '';
      const response = await fetch(`${API_BASE}/metrics/performance`, {
        headers: {
          'X-API-Key': apiKey,
        },
        signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      if (!signal?.aborted) {
        setMetrics(data);
        setError(null);
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return; // Ignore abort errors
      }
      if (!signal?.aborted) {
        setError(err instanceof Error ? err.message : 'Failed to fetch metrics');
      }
    } finally {
      if (!signal?.aborted) {
        setLoading(false);
      }
    }
  }, []);

  // Record a WebSocket message
  const recordWsMessage = useCallback(() => {
    wsMessageCount.current++;
  }, []);

  // Calculate WebSocket messages per second
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = (now - lastWsCountTime.current) / 1000;

      if (elapsed >= 1) {
        setWsMessagesPerSec(wsMessageCount.current / elapsed);
        wsMessageCount.current = 0;
        lastWsCountTime.current = now;
      }
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // Calculate render FPS using requestAnimationFrame
  useEffect(() => {
    let animationId: number;
    let isActive = true; // Guard against post-unmount execution

    const measureFps = () => {
      if (!isActive) return; // Exit early if unmounted

      frameCount.current++;

      const now = Date.now();
      const elapsed = now - lastFpsTime.current;

      if (elapsed >= 1000) {
        if (isActive) {
          setRenderFps(Math.round((frameCount.current * 1000) / elapsed));
        }
        frameCount.current = 0;
        lastFpsTime.current = now;
      }

      if (isActive) {
        animationId = requestAnimationFrame(measureFps);
      }
    };

    animationId = requestAnimationFrame(measureFps);

    return () => {
      isActive = false; // Set flag before cancel
      cancelAnimationFrame(animationId);
    };
  }, []);

  // Poll for backend metrics
  useEffect(() => {
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const doFetch = () => fetchMetrics(controller.signal);

    doFetch();
    const interval = setInterval(doFetch, pollInterval);

    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [pollInterval, fetchMetrics]);

  // Manual refresh function
  const refresh = useCallback(() => {
    // Cancel any in-flight request before starting a new one
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    fetchMetrics(controller.signal);
  }, [fetchMetrics]);

  return {
    metrics,
    frontendMetrics: {
      ws_messages_per_sec: wsMessagesPerSec,
      render_fps: renderFps,
    },
    loading,
    error,
    recordWsMessage,
    refresh,
  };
}
