import { useMotionValue, useTransform, useSpring } from 'framer-motion';
import { useEffect, useState } from 'react';

export function useParallax(
  mouseX: ReturnType<typeof useMotionValue<number>>,
  mouseY: ReturnType<typeof useMotionValue<number>>,
  factor: number = 0.05
) {
  const springConfig = { damping: 25, stiffness: 150 };

  const x = useSpring(
    useTransform(mouseX, (v) => v * factor),
    springConfig
  );
  const y = useSpring(
    useTransform(mouseY, (v) => v * factor),
    springConfig
  );

  return { x, y };
}

export function useMousePosition() {
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mouseX.set(e.clientX - window.innerWidth / 2);
      mouseY.set(e.clientY - window.innerHeight / 2);
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [mouseX, mouseY]);

  return { mouseX, mouseY };
}
