'use client';

import { useState } from 'react';
import { WebcamASCII } from '@/app/components/WebcamASCII';
import styles from './test-webcam.module.css';

export default function TestWebcamPage() {
  const [isLoading, setIsLoading] = useState(true);

  return (
    <div className={styles.page}>
      {/* Webcam ASCII Loading Overlay */}
      <WebcamASCII 
        isLoading={isLoading} 
        message="INITIALIZING DASHBOARD..." 
      />

      {/* Main Content - Shown after loading */}
      <div className={styles.content}>
        <h1 className={styles.title}>WEBCAM ASCII TEST</h1>
        <p className={styles.subtitle}>Reload page to see loading animation again</p>
        
        <button 
          className={styles.reloadBtn}
          onClick={() => {
            setIsLoading(true);
            setTimeout(() => setIsLoading(false), 5000);
          }}
        >
          SHOW LOADING AGAIN (5s)
        </button>

        <div className={styles.info}>
          <h3>HOW IT WORKS:</h3>
          <ul>
            <li>Accesses your webcam</li>
            <li>Captures video frames</li>
            <li>Converts to ASCII characters</li>
            <li>Displays as loading animation</li>
            <li>Fallback if no camera available</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
