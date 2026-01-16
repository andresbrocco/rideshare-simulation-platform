import { useState, useCallback } from 'react';
import { useDraggable } from '../../hooks/useDraggable';
import styles from './Inspector.module.css';

interface DraggablePopupContainerProps {
  x: number;
  y: number;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

export function DraggablePopupContainer({
  x,
  y,
  title,
  onClose,
  children,
}: DraggablePopupContainerProps) {
  const [isMinimized, setIsMinimized] = useState(false);
  const { position, isDragging, handleMouseDown } = useDraggable({
    initialX: x,
    initialY: y,
    popupWidth: 320,
    popupHeight: 100,
  });

  const handleHeaderMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if ((e.target as HTMLElement).closest(`.${styles.dragHandle}`)) {
        handleMouseDown(e);
      }
    },
    [handleMouseDown]
  );

  return (
    <div
      className={`${styles.popup} ${isDragging ? styles.dragging : ''} ${isMinimized ? styles.minimized : ''}`}
      data-testid="inspector-popup"
      style={{
        left: position.x,
        top: position.y,
      }}
    >
      <div className={styles.popupHeader} onMouseDown={handleHeaderMouseDown}>
        <div className={styles.dragHandle}>
          <span className={styles.dragIcon}>:::::</span>
        </div>
        <button
          className={styles.minimizeButton}
          onClick={() => setIsMinimized(!isMinimized)}
          aria-label={isMinimized ? 'Restore' : 'Minimize'}
        >
          {isMinimized ? '[]' : '-'}
        </button>
        <button className={styles.closeButton} onClick={onClose} aria-label="Close">
          x
        </button>
      </div>
      {isMinimized && (
        <div className={styles.minimizedHeader}>
          <span className={styles.minimizedTitle}>{title}</span>
        </div>
      )}
      <div className={styles.popupContent} style={{ display: isMinimized ? 'none' : undefined }}>
        {children}
      </div>
    </div>
  );
}
