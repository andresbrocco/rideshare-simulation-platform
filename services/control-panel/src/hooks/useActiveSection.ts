import { useEffect, useRef, useState } from 'react';

/**
 * Tracks which section is most visible in the viewport.
 *
 * `sectionIds` must be a stable reference (define with `as const` or
 * wrap in `useMemo`) to avoid re-creating the observer on every render.
 */
export function useActiveSection(sectionIds: readonly string[]): string | null {
  const [activeId, setActiveId] = useState<string | null>(null);
  const ratiosRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    ratiosRef.current = new Map(sectionIds.map((id) => [id, 0]));

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          ratiosRef.current.set(entry.target.id, entry.intersectionRatio);
        }

        let maxRatio = 0;
        let maxId: string | null = null;
        for (const [id, ratio] of ratiosRef.current) {
          if (ratio > maxRatio) {
            maxRatio = ratio;
            maxId = id;
          }
        }

        setActiveId(maxId);
      },
      {
        rootMargin: '-20% 0% -20% 0%',
        threshold: [0, 0.25, 0.5, 0.75, 1],
      }
    );

    for (const id of sectionIds) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }

    return () => {
      observer.disconnect();
    };
  }, [sectionIds]);

  return activeId;
}
