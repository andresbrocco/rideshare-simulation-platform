import { useEffect, useRef, useState } from 'react';

type EasingFn = (t: number) => number;

const easeOutExpo: EasingFn = (t) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t));

interface UseCountUpOptions {
  target: number;
  duration?: number;
  easing?: EasingFn;
  start?: boolean;
}

export function useCountUp({
  target,
  duration = 1800,
  easing = easeOutExpo,
  start = true,
}: UseCountUpOptions): number {
  const [count, setCount] = useState(0);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  useEffect(() => {
    if (!start || prefersReducedMotion) return;

    startTimeRef.current = null;

    const tick = (timestamp: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp;
      }
      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      setCount(Math.round(easing(progress) * target));

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [target, duration, easing, start, prefersReducedMotion]);

  if (!start) return 0;
  if (prefersReducedMotion) return target;
  return count;
}
