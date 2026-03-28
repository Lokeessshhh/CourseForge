'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import styles from './WebcamASCII.module.css';

interface WebcamASCIIProps {
  isLoading: boolean;
  message?: string;
}

export function WebcamASCII({ isLoading, message = 'LOADING DASHBOARD...' }: WebcamASCIIProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [asciiFrame, setAsciiFrame] = useState<string>('');
  const [cameraError, setCameraError] = useState(false);

  useEffect(() => {
    if (!isLoading) return;

    let stream: MediaStream | null = null;
    let animationFrameId: number;

    const startCamera = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 128, height: 96 },
        });

        if (videoRef.current && stream) {
          videoRef.current.srcObject = stream;
        }
      } catch (err) {
        console.log('Camera not available, using fallback');
        setCameraError(true);
      }
    };

    startCamera();

    const captureFrame = () => {
      if (!canvasRef.current || !videoRef.current) {
        animationFrameId = requestAnimationFrame(captureFrame);
        return;
      }

      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');

      if (!ctx || video.readyState !== 4) {
        animationFrameId = requestAnimationFrame(captureFrame);
        return;
      }

      // Draw video frame to canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      // Convert to ASCII
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const ascii = convertToASCII(imageData);
      setAsciiFrame(ascii);

      animationFrameId = requestAnimationFrame(captureFrame);
    };

    if (!cameraError) {
      captureFrame();
    }

    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
      }
    };
  }, [isLoading, cameraError]);

  const convertToASCII = (imageData: ImageData): string => {
    const { width, height, data } = imageData;
    const asciiChars = ' .:-=+*#%@';
    let ascii = '';

    for (let y = 0; y < height; y += 2) {
      for (let x = 0; x < width; x++) {
        const i = (y * width + x) * 4;
        const avg = (data[i] + data[i + 1] + data[i + 2]) / 3;
        const charIndex = Math.floor((avg / 255) * (asciiChars.length - 1));
        ascii += asciiChars[charIndex];
      }
      ascii += '\n';
    }

    return ascii;
  };

  // Fallback animation when camera is not available
  const renderFallbackASCII = () => {
    const frames = [
      `
    ██████╗ ██╗   ██╗██████╗ 
    ██╔══██╗██║   ██║██╔══██╗
    ██████╔╝██║   ██║██████╔╝
    ██╔══██╗██║   ██║██╔══██╗
    ██████╔╝╚██████╔╝██████╔╝
    ╚═════╝  ╚═════╝ ╚═════╝ 
      `,
      `
    ██████╗ ██╗   ██╗██████╗ ███████╗
    ██╔══██╗██║   ██║██╔══██╗██╔════╝
    ██████╔╝██║   ██║██████╔╝█████╗  
    ██╔══██╗██║   ██║██╔══██╗██╔══╝  
    ██████╔╝╚██████╔╝██║  ██║███████╗
    ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝
      `,
      `
    ██████╗ ██╗   ██╗██████╗ ███████╗██████╗ 
    ██╔══██╗██║   ██║██╔══██╗██╔════╝██╔══██╗
    ██████╔╝██║   ██║██████╔╝█████╗  ██████╔╝
    ██╔══██╗██║   ██║██╔══██╗██╔══╝  ██╔══██╗
    ██████╔╝╚██████╔╝██║  ██║███████╗██║  ██║
    ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
      `,
    ];

    return frames[Math.floor(Date.now() / 500) % frames.length];
  };

  if (!isLoading) return null;

  return (
    <AnimatePresence>
      <motion.div
        className={styles.overlay}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0, scale: 1.1 }}
        transition={{ duration: 0.3 }}
      >
        <motion.div
          className={styles.container}
          initial={{ scale: 0.8, y: 50 }}
          animate={{ scale: 1, y: 0 }}
          transition={{ duration: 0.5, type: 'spring' }}
        >
          {/* ASCII Art Display */}
          <div className={styles.asciiDisplay}>
            {cameraError ? (
              <pre className={styles.asciiText}>{renderFallbackASCII()}</pre>
            ) : (
              <>
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className={styles.hiddenVideo}
                />
                <canvas
                  ref={canvasRef}
                  width={128}
                  height={96}
                  className={styles.hiddenCanvas}
                />
                <pre className={styles.asciiText}>{asciiFrame}</pre>
              </>
            )}
          </div>

          {/* Loading Message */}
          <div className={styles.loadingMessage}>
            <motion.div
              className={styles.dots}
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            >
              {message}
            </motion.div>
            <div className={styles.progressBar}>
              <motion.div
                className={styles.progressFill}
                animate={{ x: ['-100%', '100%'] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
              />
            </div>
          </div>

          {/* Decorative Elements */}
          <div className={styles.cornerTL} />
          <div className={styles.cornerTR} />
          <div className={styles.cornerBL} />
          <div className={styles.cornerBR} />
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
