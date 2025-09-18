import { useEffect, useLayoutEffect, useRef, useState, useCallback } from 'react';

interface UseWebSocketOptions {
  url: string;
  apiKey: string;
  onMessage: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
}

interface EventCache {
  eventIds: Set<string>;
  maxSize: number;
}

const createEventCache = (maxSize: number = 1000): EventCache => ({
  eventIds: new Set(),
  maxSize,
});

export function useWebSocket({
  url,
  apiKey,
  onMessage,
  onOpen,
  onClose,
  onError,
}: UseWebSocketOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);
  const onErrorRef = useRef(onError);
  const isCleanedUpRef = useRef(false);
  const eventCacheRef = useRef(createEventCache(1000));

  // Update refs in useLayoutEffect (runs before regular useEffect)
  // This ensures the refs have the latest callbacks when the WebSocket
  // connection effect runs and receives messages
  useLayoutEffect(() => {
    onMessageRef.current = onMessage;
    onOpenRef.current = onOpen;
    onCloseRef.current = onClose;
    onErrorRef.current = onError;
  });

  useEffect(() => {
    // Don't attempt connection without a valid API key
    if (!apiKey) {
      return;
    }

    isCleanedUpRef.current = false;

    const doConnect = () => {
      // Don't connect if effect was cleaned up
      if (isCleanedUpRef.current) return;

      const ws = new WebSocket(`${url}?api_key=${apiKey}`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (isCleanedUpRef.current) {
          ws.close();
          return;
        }
        setIsConnected(true);
        onOpenRef.current?.();
      };

      ws.onmessage = (event) => {
        if (isCleanedUpRef.current) return;
        try {
          const data = JSON.parse(event.data);

          // Deduplicate events by event_id
          const eventId = (data as Record<string, unknown>)?.event_id;
          if (typeof eventId === 'string' && eventId) {
            const cache = eventCacheRef.current;
            if (cache.eventIds.has(eventId)) {
              return; // Skip duplicate
            }
            // LRU eviction: remove oldest if at capacity
            if (cache.eventIds.size >= cache.maxSize) {
              const oldest = cache.eventIds.values().next().value;
              if (oldest) cache.eventIds.delete(oldest);
            }
            cache.eventIds.add(eventId);
          }

          onMessageRef.current(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onclose = () => {
        if (isCleanedUpRef.current) return;
        setIsConnected(false);
        onCloseRef.current?.();

        reconnectTimeoutRef.current = setTimeout(() => {
          doConnect();
        }, 3000);
      };

      ws.onerror = (error) => {
        if (isCleanedUpRef.current) return;
        console.error('WebSocket error:', error);
        onErrorRef.current?.(error);
      };
    };

    doConnect();

    return () => {
      isCleanedUpRef.current = true;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [url, apiKey]);

  const sendMessage = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { isConnected, sendMessage };
}
