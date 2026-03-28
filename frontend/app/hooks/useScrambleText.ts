import { useState, useEffect, useRef } from 'react';

const SCRAMBLE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ#@%&*';

export function useScrambleText(
  text: string,
  options: {
    duration?: number;
    delay?: number;
    chars?: string;
  } = {}
) {
  const { duration = 800, delay = 0, chars = SCRAMBLE_CHARS } = options;
  const [displayText, setDisplayText] = useState('');
  const [isScrambling, setIsScrambling] = useState(false);
  const hasStarted = useRef(false);

  useEffect(() => {
    if (hasStarted.current) return;
    hasStarted.current = true;

    const timeout = setTimeout(() => {
      setIsScrambling(true);
      const startTime = Date.now();
      const interval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);

        let result = '';
        for (let i = 0; i < text.length; i++) {
          if (progress > i / text.length) {
            result += text[i];
          } else {
            result += chars[Math.floor(Math.random() * chars.length)];
          }
        }
        setDisplayText(result);

        if (progress >= 1) {
          clearInterval(interval);
          setDisplayText(text);
          setIsScrambling(false);
        }
      }, 30);

      return () => clearInterval(interval);
    }, delay);

    return () => clearTimeout(timeout);
  }, [text, duration, delay, chars]);

  return { displayText, isScrambling };
}
