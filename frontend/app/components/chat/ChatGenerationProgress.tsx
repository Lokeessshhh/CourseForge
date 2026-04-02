'use client';

import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '@clerk/nextjs';
import { useSSEProgress } from '@/app/hooks/api/useSSEProgress';
import { useGenerationProgress } from '@/app/context/GenerationProgressContext';
import styles from './ChatGenerationProgress.module.css';

interface Props {
  courseId: string;
  courseName: string;
  onComplete?: () => void;
  onCancel?: () => void;
}

interface PollingData {
  progress: number;
  completed_days: number;
  total_days: number;
  generation_status: 'pending' | 'generating' | 'ready' | 'failed' | 'updating';
  current_stage?: string;
  topic?: string;
}

export default function ChatGenerationProgress({ courseId, courseName, onComplete, onCancel }: Props) {
  const { getToken } = useAuth();
  const [isPolling, setIsPolling] = useState(false);
  const [pollingData, setPollingData] = useState<PollingData | null>(null);
  const [hasCompleted, setHasCompleted] = useState(false);
  const [initialTotalDays, setInitialTotalDays] = useState<number | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const hasCompletedRef = useRef(false);
  const sseDidConnectRef = useRef(false);

  const { updateGeneratingCourse, getGeneratingCourse, removeGeneratingCourse } = useGenerationProgress();
  const { data, isConnected, error, disconnect } = useSSEProgress(courseId, true);

  // Get course data from global context (source of truth)
  const contextCourse = getGeneratingCourse(courseId);

  // Use context data as primary source, SSE/polling as secondary
  const activeData = contextCourse || (isPolling && pollingData ? pollingData : data);

  // Store initial total_days when data first arrives
  useEffect(() => {
    if (activeData?.total_days && !initialTotalDays) {
      setInitialTotalDays(activeData.total_days);
    }
  }, [activeData?.total_days, initialTotalDays]);

  // Track if SSE ever connected
  useEffect(() => {
    if (isConnected) {
      sseDidConnectRef.current = true;
    }
  }, [isConnected]);

  // Update global context with SSE/polling data (context is source of truth)
  useEffect(() => {
    const sseOrPollingData = isPolling && pollingData ? pollingData : data;
    if (sseOrPollingData) {
      console.log('[ChatGenerationProgress] Updating context with:', sseOrPollingData);
      updateGeneratingCourse(courseId, {
        progress: sseOrPollingData.progress,
        completed_days: sseOrPollingData.completed_days,
        total_days: sseOrPollingData.total_days,
        generation_status: sseOrPollingData.generation_status,
        current_stage: sseOrPollingData.current_stage,
        topic: sseOrPollingData.topic,
      });
    }
  }, [data, pollingData, isPolling, courseId, updateGeneratingCourse]);

  // Switch to polling if SSE disconnects early
  useEffect(() => {
    if (hasCompleted || hasCompletedRef.current || contextCourse?.generation_status === 'ready') return;

    const shouldSwitchToPolling =
      !isConnected &&
      sseDidConnectRef.current &&
      (error || !data) &&
      data?.generation_status !== 'ready' &&
      data?.generation_status !== 'failed';

    if (shouldSwitchToPolling && !isPolling) {
      console.log('[ChatGenerationProgress] SSE disconnected, switching to polling...');
      setIsPolling(true);
    }
  }, [isConnected, error, data, isPolling, hasCompleted, contextCourse]);

  // Polling logic
  useEffect(() => {
    if (!isPolling || hasCompleted || hasCompletedRef.current || contextCourse?.generation_status === 'ready') return;

    console.log('[ChatGenerationProgress] Starting polling...');

    const poll = async () => {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${baseUrl}/api/courses/${courseId}/generation-progress/`);

        if (!response.ok) return;

        const result = await response.json();
        const progressData: PollingData = result.data || result;

        setPollingData(progressData);

        if (
          progressData.generation_status === 'ready' ||
          progressData.progress === 100 ||
          progressData.generation_status === 'failed'
        ) {
          handleCompletion(progressData);
        }
      } catch (err) {
        console.error('[ChatGenerationProgress] Polling error:', err);
      }
    };

    poll();
    pollIntervalRef.current = setInterval(poll, 3000);

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [isPolling, courseId, hasCompleted, contextCourse]);

  const handleCompletion = (completionData: PollingData) => {
    if (hasCompletedRef.current) return;

    hasCompletedRef.current = true;
    setHasCompleted(true);

    console.log('[ChatGenerationProgress] Generation complete!');

    // Stop polling and SSE
    disconnect();
    setIsPolling(false);
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    // Update context as complete - DON'T remove from context
    updateGeneratingCourse(courseId, {
      generation_status: completionData.generation_status,
      progress: completionData.progress || 100,
    });

    // Don't remove from context - keep the progress bar visible
  };

  // Handle SSE completion
  useEffect(() => {
    if (
      (data?.generation_status === 'ready' || data?.progress === 100) &&
      !hasCompleted &&
      !hasCompletedRef.current
    ) {
      handleCompletion(data);
    }
  }, [data?.generation_status, data?.progress, hasCompleted]);

  // Handle failure
  useEffect(() => {
    if (data?.generation_status === 'failed' && !hasCompleted && !hasCompletedRef.current) {
      handleCompletion(data);
    }
  }, [data?.generation_status, hasCompleted]);

  // Check if already completed from context on mount
  useEffect(() => {
    if (contextCourse?.generation_status === 'ready' && !hasCompleted && !hasCompletedRef.current) {
      hasCompletedRef.current = true;
      setHasCompleted(true);
    }
  }, [contextCourse?.generation_status, hasCompleted]);

  // Cancel generation
  const handleCancel = async () => {
    if (isCancelling) return;
    
    setIsCancelling(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = await getToken();
      
      const response = await fetch(`${baseUrl}/api/courses/${courseId}/cancel-generation/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        // Remove from context
        removeGeneratingCourse(courseId);
        // Notify parent
        if (onCancel) onCancel();
        console.log('[ChatGenerationProgress] Generation cancelled');
      } else {
        console.error('[ChatGenerationProgress] Failed to cancel generation');
      }
    } catch (err) {
      console.error('[ChatGenerationProgress] Cancel error:', err);
    } finally {
      setIsCancelling(false);
    }
  };

  // Cleanup
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const isFailed = activeData?.generation_status === 'failed';
  const isComplete = activeData?.generation_status === 'ready' || activeData?.progress === 100 || hasCompleted;
  const isInitializing = activeData?.generation_status === 'pending';
  const progress = activeData?.progress || 0;

  // Use total_days directly from backend (already calculated correctly for updates)
  const totalDayTasks = activeData?.total_days || 20;
  // Calculate tests based on weeks (5 days per week, 2 tests per week)
  const totalWeeksForTests = Math.ceil(totalDayTasks / 5);
  const totalTestTasks = totalWeeksForTests * 2;

  return (
    <motion.div
      className={`${styles.container} ${isComplete ? styles.complete : ''} ${isFailed ? styles.failed : ''} ${isInitializing ? styles.initializing : ''}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <div>
            <h3 className={styles.title}>
              {isComplete
                ? 'Course Generated Successfully'
                : isFailed
                ? 'Generation Failed'
                : isInitializing
                ? 'Initializing Course Generation...'
                : `Generating: ${courseName}`}
            </h3>
            {!isComplete && !isFailed && activeData?.current_stage && (
              <p className={styles.stage}>{activeData.current_stage}</p>
            )}
          </div>
        </div>
        <div className={styles.headerRight}>
          {!isComplete && !isFailed && (
            <button
              className={styles.cancelBtn}
              onClick={handleCancel}
              disabled={isCancelling}
              type="button"
            >
              {isCancelling ? 'Stopping...' : 'Stop'}
            </button>
          )}
          <span className={styles.progressPercent}>{isInitializing ? '...' : `${Math.round(progress)}%`}</span>
        </div>
      </div>

      <div className={styles.progressBar}>
        {isInitializing ? (
          <motion.div
            className={`${styles.progressFill} ${styles.indeterminate}`}
            animate={{ x: ['-100%', '100%'] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
          />
        ) : (
          <motion.div
            className={styles.progressFill}
            initial={{ width: 0 }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.5 }}
          />
        )}
      </div>

      <div className={styles.footer}>
        <span className={styles.details}>
          {activeData?.completed_days || 0} / {totalDayTasks} days + {totalTestTasks} tests
        </span>
        <span className={`${styles.status} ${isComplete ? styles.statusComplete : isFailed ? styles.statusFailed : ''}`}>
          {isComplete ? 'READY' : isFailed ? 'FAILED' : activeData?.generation_status === 'pending' ? 'INITIALIZING' : activeData?.generation_status || 'generating'}
        </span>
      </div>

      {isComplete && (
        <motion.div
          className={styles.successMessage}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
        >
          <p>Your course is ready to start learning</p>
        </motion.div>
      )}

      {isPolling && !isComplete && (
        <div className={styles.pollingIndicator}>Polling for updates...</div>
      )}
    </motion.div>
  );
}
