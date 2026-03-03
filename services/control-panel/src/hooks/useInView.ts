import { useEffect, useRef, useState } from 'react';

export interface UseInViewOptions {
  threshold?: number | number[];
  rootMargin?: string;
  triggerOnce?: boolean;
}

export function useInView<T extends Element>(
  options: UseInViewOptions = {}
): [React.RefObject<T | null>, boolean] {
  const { threshold = 0, rootMargin = '0px', triggerOnce = false } = options;
  const ref = useRef<T | null>(null);
  const [isInView, setIsInView] = useState(false);
  const observerRef = useRef<IntersectionObserver | null>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    observerRef.current = new IntersectionObserver(
      ([entry]) => {
        const visible = entry.isIntersecting;
        setIsInView(visible);
        if (visible && triggerOnce && observerRef.current) {
          observerRef.current.disconnect();
        }
      },
      { threshold, rootMargin }
    );

    observerRef.current.observe(element);

    return () => {
      observerRef.current?.disconnect();
    };
  }, [threshold, rootMargin, triggerOnce]);

  return [ref, isInView];
}
