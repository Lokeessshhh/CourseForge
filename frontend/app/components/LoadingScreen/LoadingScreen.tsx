'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import styles from './LoadingScreen.module.css';

export default function LoadingScreen() {
  const [isLoading, setIsLoading] = useState(true);
  const [displayText, setDisplayText] = useState('');
  const fullText = 'CourseForge';

  useEffect(() => {
    // Check if already shown in this session
    if (sessionStorage.getItem('loadingShown')) {
      setIsLoading(false);
      return;
    }

    // Typewriter effect
    let charIndex = 0;
    const typeInterval = setInterval(() => {
      if (charIndex <= fullText.length) {
        setDisplayText(fullText.slice(0, charIndex));
        charIndex++;
      } else {
        clearInterval(typeInterval);
        
        // Flash and hide
        setTimeout(() => {
          sessionStorage.setItem('loadingShown', 'true');
          setIsLoading(false);
        }, 400);
      }
    }, 100);

    return () => clearInterval(typeInterval);
  }, []);

  return (
    <AnimatePresence>
      {isLoading && (
        <motion.div
          className={styles.overlay}
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
        >
          <motion.div
            className={styles.text}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
          >
            {displayText}
            <span className={styles.cursor}>|</span>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
