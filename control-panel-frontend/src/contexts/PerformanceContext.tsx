import { useState, useEffect, useCallback, useRef } from 'react';
import type { ReactNode } from 'react';
import type { FrontendMetrics } from '../types/api';
import { PerformanceContext } from './performanceContextDef';

interface PerformanceProviderProps {
  children: ReactNode;
}

export function PerformanceProvider({ children }: PerformanceProviderProps) {
  // Frontend metrics tracking
  const [wsMessagesPerSec, setWsMessagesPerSec] = useState(0);
  const [renderFps, setRenderFps] = useState(60);

  // Message count tracking - initialized in useEffect to avoid impure render
  const wsMessageCount = useRef(0);
  const lastWsCountTime = useRef<number | null>(null);

  // FPS tracking - initialized in useEffect to avoid impure render
  const frameCount = useRef(0);
  const lastFpsTime = useRef<number | null>(null);

  // Record a WebSocket message
  const recordWsMessage = useCallback(() => {
    wsMessageCount.current++;
  }, []);

  // Calculate WebSocket messages per second
  useEffect(() => {
    // Initialize time reference on mount
    lastWsCountTime.current = Date.now();

    const interval = setInterval(() => {
      const now = Date.now();
      const elapsed = (now - (lastWsCountTime.current ?? now)) / 1000;

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
    let isActive = true;

    // Initialize time reference on mount
    lastFpsTime.current = Date.now();

    const measureFps = () => {
      if (!isActive) return;

      frameCount.current++;

      const now = Date.now();
      const elapsed = now - (lastFpsTime.current ?? now);

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
      isActive = false;
      cancelAnimationFrame(animationId);
    };
  }, []);

  const frontendMetrics: FrontendMetrics = {
    ws_messages_per_sec: wsMessagesPerSec,
    render_fps: renderFps,
  };

  return (
    <PerformanceContext.Provider value={{ frontendMetrics, recordWsMessage }}>
      {children}
    </PerformanceContext.Provider>
  );
}
