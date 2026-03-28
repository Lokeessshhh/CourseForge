import { useEffect, useState, useCallback } from 'react';

export function useKeySequence(
  targetSequence: string[],
  onMatch: () => void
) {
  const [inputSequence, setInputSequence] = useState<string[]>([]);

  const resetSequence = useCallback(() => {
    setInputSequence([]);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const key = e.key.toUpperCase();
      const newSequence = [...inputSequence, key].slice(-targetSequence.length);
      setInputSequence(newSequence);

      if (JSON.stringify(newSequence) === JSON.stringify(targetSequence)) {
        onMatch();
        resetSequence();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [inputSequence, targetSequence, onMatch, resetSequence]);

  return { resetSequence };
}
