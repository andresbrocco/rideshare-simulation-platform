import { useState, useId, useRef, ReactElement, cloneElement } from 'react';
import styles from './Tooltip.module.css';

interface TooltipProps {
  text: string;
  position?: 'top' | 'bottom' | 'left' | 'right';
  children: ReactElement;
}

export default function Tooltip({ text, position = 'top', children }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const wrapperRef = useRef<HTMLDivElement>(null);
  const tooltipId = useId();

  const handleMouseEnter = () => {
    if (wrapperRef.current) {
      const rect = wrapperRef.current.getBoundingClientRect();
      const offset = 8;
      let top = 0,
        left = 0;

      if (position === 'top') {
        top = rect.top - offset;
        left = rect.left + rect.width / 2;
      } else if (position === 'bottom') {
        top = rect.bottom + offset;
        left = rect.left + rect.width / 2;
      } else if (position === 'left') {
        top = rect.top + rect.height / 2;
        left = rect.left - offset;
      } else {
        top = rect.top + rect.height / 2;
        left = rect.right + offset;
      }
      setCoords({ top, left });
    }
    setIsVisible(true);
  };

  const childWithProps = cloneElement(children, {
    'aria-describedby': isVisible ? tooltipId : undefined,
  });

  return (
    <div
      ref={wrapperRef}
      className={styles.wrapper}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={() => setIsVisible(false)}
    >
      {childWithProps}
      {isVisible && (
        <div
          id={tooltipId}
          role="tooltip"
          className={`${styles.tooltip} ${styles[position]} ${styles.visible}`}
          style={{ top: coords.top, left: coords.left }}
        >
          {text}
          <div className={styles.arrow} />
        </div>
      )}
    </div>
  );
}
