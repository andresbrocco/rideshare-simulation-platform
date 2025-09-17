import { useState, useCallback, useRef, useEffect } from 'react';

interface UseDraggableOptions {
  initialX: number;
  initialY: number;
  popupWidth?: number;
  popupHeight?: number;
}

interface UseDraggableReturn {
  position: { x: number; y: number };
  isDragging: boolean;
  handleMouseDown: (e: React.MouseEvent) => void;
}

export function useDraggable({
  initialX,
  initialY,
  popupWidth = 320,
  popupHeight = 100,
}: UseDraggableOptions): UseDraggableReturn {
  const [position, setPosition] = useState({ x: initialX, y: initialY });
  const [isDragging, setIsDragging] = useState(false);
  const dragOffsetRef = useRef({ x: 0, y: 0 });
  const prevInitialRef = useRef({ x: initialX, y: initialY });

  // Reset position when initial coordinates change (new entity selected)
  // eslint-disable-next-line react-hooks/refs
  if (prevInitialRef.current.x !== initialX || prevInitialRef.current.y !== initialY) {
    // eslint-disable-next-line react-hooks/refs
    prevInitialRef.current = { x: initialX, y: initialY };
    setPosition({ x: initialX, y: initialY });
  }

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsDragging(true);
      dragOffsetRef.current = {
        x: e.clientX - position.x,
        y: e.clientY - position.y,
      };
    },
    [position.x, position.y]
  );

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      setPosition({
        x: Math.max(
          0,
          Math.min(window.innerWidth - popupWidth, e.clientX - dragOffsetRef.current.x)
        ),
        y: Math.max(
          0,
          Math.min(window.innerHeight - popupHeight, e.clientY - dragOffsetRef.current.y)
        ),
      });
    },
    [popupWidth, popupHeight]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  return {
    position,
    isDragging,
    handleMouseDown,
  };
}
