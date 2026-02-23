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
  const [positionState, setPositionState] = useState({
    x: initialX,
    y: initialY,
    sourceX: initialX,
    sourceY: initialY,
  });
  const [isDragging, setIsDragging] = useState(false);
  const dragOffsetRef = useRef({ x: 0, y: 0 });

  // Reset position when initial coordinates change (new entity selected)
  // This is the React-recommended render-phase setState pattern for prop-driven resets.
  if (positionState.sourceX !== initialX || positionState.sourceY !== initialY) {
    setPositionState({ x: initialX, y: initialY, sourceX: initialX, sourceY: initialY });
  }

  const position = { x: positionState.x, y: positionState.y };

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
      setPositionState((prev) => ({
        ...prev,
        x: Math.max(
          0,
          Math.min(window.innerWidth - popupWidth, e.clientX - dragOffsetRef.current.x)
        ),
        y: Math.max(
          0,
          Math.min(window.innerHeight - popupHeight, e.clientY - dragOffsetRef.current.y)
        ),
      }));
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
