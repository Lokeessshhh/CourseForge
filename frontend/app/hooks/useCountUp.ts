import { useMotionValue, animate, useMotionValueEvent } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';

export function useCountUp(
  target: number,
  options: {
    duration?: number;
    startOnView?: boolean;
  } = {}
) {
  const { duration = 1.5, startOnView = true } = options;
  const motionValue = useMotionValue(0);
  const [displayValue, setDisplayValue] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const hasAnimated = useRef(false);

  useEffect(() => {
    if (!startOnView || !ref.current) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          animate(motionValue, target, { duration });
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [motionValue, target, duration, startOnView]);

  useMotionValueEvent(motionValue, 'change', (latest) => {
    setDisplayValue(Math.round(latest * 10) / 10);
  });

  const start = () => {
    if (!hasAnimated.current) {
      hasAnimated.current = true;
      animate(motionValue, target, { duration });
    }
  };

  return { ref, displayValue, motionValue, start };
}
