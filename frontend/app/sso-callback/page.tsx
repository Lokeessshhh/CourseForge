'use client';

import { useEffect, useState } from 'react';
import { AuthenticateWithRedirectCallback } from '@clerk/nextjs';
import { motion } from 'framer-motion';
import styles from './page.module.css';

export default function SsoCallbackPage() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((p) => (p >= 100 ? 0 : p + 2));
    }, 50);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className={styles.page}>
      <div className={styles.container}>
        <motion.h1
          className={styles.title}
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          COURSEFORGE
        </motion.h1>
        <div className={styles.progressContainer}>
          <motion.div
            className={styles.progressBar}
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className={styles.text}>Completing sign in...</p>
      </div>
      <AuthenticateWithRedirectCallback />
    </div>
  );
}
