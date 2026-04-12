'use client';

import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSSEProgress } from '@/app/hooks/api/useSSEProgress';
import styles from './GenerationProgressToast.module.css';

interface Props {
  courseId: string;
  onDismiss: () => void;
  onGenerationComplete?: () => void;
}

interface PollingData {
  progress: number;
  completed_days: number;
  total_days: number;
  generation_status: 'pending' | 'generating' | 'ready' | 'failed' | 'updating';
  current_stage?: string;
  topic?: string;
  weeks?: any[];
}

export default function GenerationProgressToast({ courseId, onDismiss, onGenerationComplete }: Props) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [hasCompleted, setHasCompleted] = useState(false);
  const [connectionAttempts, setConnectionAttempts] = useState(0);
  const [isDisconnected, setIsDisconnected] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [pollingData, setPollingData] = useState<PollingData | null>(null);
  
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const dismissTimerRef = useRef<NodeJS.Timeout | null>(null);
  const hasCompletedRef = useRef(false);
  const sseDidConnectRef = useRef(false);

  // Use SSE for real-time progress updates - SSE is the source of truth
  const { data, isConnected, error, disconnect, reconnect } = useSSEProgress(courseId, true);

  // Track if SSE ever connected successfully
  useEffect(() => {
    if (isConnected) {
      sseDidConnectRef.current = true;
    }
  }, [isConnected]);

  // CRITICAL FIX: Detect SSE disconnection when NOT already completed
  useEffect(() => {
    if (!isConnected && sseDidConnectRef.current && !hasCompleted && !hasCompletedRef.current) {
      console.log('[GenerationProgressToast] SSE disconnected before completion');
      setIsDisconnected(true);
    }
  }, [isConnected, hasCompleted]);

  // HYBRID APPROACH: Start polling if SSE disconnects before completion
  useEffect(() => {
    // Don't poll if already completed
    if (hasCompleted || hasCompletedRef.current) {
      return;
    }

    // Check if we should switch to polling
    const shouldSwitchToPolling =
      !isConnected &&
      sseDidConnectRef.current &&
      (isDisconnected || error) &&
      data?.generation_status !== 'ready' &&
      data?.generation_status !== 'failed';

    if (shouldSwitchToPolling && !isPolling) {
      console.log('[GenerationProgressToast] SSE disconnected early, switching to polling...');
      setIsPolling(true);
    }
  }, [isConnected, isDisconnected, error, data?.generation_status, isPolling, hasCompleted]);

  // SAFETY TIMEOUT: Auto-dismiss after 30 seconds regardless of state
  useEffect(() => {
    if (hasCompleted || hasCompletedRef.current) return;

    const safetyTimeout = setTimeout(() => {
      console.log('[GenerationProgressToast] 30s safety timeout - auto-dismissing');
      handleCompletion({
        progress: 100,
        completed_days: 0,
        total_days: 0,
        generation_status: 'ready',
        current_stage: 'Completed (safety timeout)',
      });
    }, 30000);

    return () => clearTimeout(safetyTimeout);
  }, [hasCompleted]);

  // Polling logic - fallback when SSE disconnects early
  useEffect(() => {
    if (!isPolling || hasCompleted || hasCompletedRef.current) {
      return;
    }

    console.log('[GenerationProgressToast] Starting polling fallback...');

    const poll = async () => {
      try {
        const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
        const response = await fetch(`${baseUrl}/api/courses/${courseId}/generation-progress/`);
        
        if (!response.ok) {
          console.log('[GenerationProgressToast] Polling failed, will retry...');
          return;
        }

        const result = await response.json();
        const progressData: PollingData = result.data || result;

        console.log('[GenerationProgressToast] Polling update:', progressData);
        setPollingData(progressData);

        // Check for completion
        if (progressData.generation_status === 'ready' || 
            progressData.progress === 100 ||
            progressData.generation_status === 'failed') {
          
          console.log('[GenerationProgressToast] Polling detected completion!');
          handleCompletion(progressData);
        }
      } catch (err) {
        console.error('[GenerationProgressToast] Polling error:', err);
      }
    };

    // Initial poll immediately
    poll();

    // Then poll every 3 seconds
    pollIntervalRef.current = setInterval(poll, 3000);

    // Cleanup
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [isPolling, courseId, hasCompleted]);

  // Handle completion (called from both SSE and polling)
  const handleCompletion = (completionData: PollingData) => {
    if (hasCompletedRef.current) {
      return; // Already handled
    }

    hasCompletedRef.current = true;
    setHasCompleted(true);
    console.log('[GenerationProgressToast] Generation complete!');

    // Stop SSE and polling
    disconnect();
    setIsPolling(false);
    setIsDisconnected(true);
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    // Clear any existing dismiss timer
    if (dismissTimerRef.current) {
      clearTimeout(dismissTimerRef.current);
    }

    // Wait 3 seconds to show completion state, then dismiss
    dismissTimerRef.current = setTimeout(() => {
      console.log('[GenerationProgressToast] Auto-dismissing toast');
      if (onGenerationComplete) {
        onGenerationComplete();
      }
      onDismiss();
    }, 3000);
  };

  // Handle completion from SSE or polling
  useEffect(() => {
    const activeStatus = isPolling && pollingData
      ? pollingData.generation_status
      : data?.generation_status;

    const activeProgress = isPolling && pollingData
      ? pollingData.progress
      : data?.progress;

    if ((activeStatus === 'ready' || activeProgress === 100) && !hasCompleted && !hasCompletedRef.current) {
      handleCompletion(isPolling && pollingData ? pollingData : data!);
    }
  }, [data?.generation_status, data?.progress, pollingData?.generation_status, pollingData?.progress, hasCompleted, isPolling, pollingData]);

  // Handle failed generation
  useEffect(() => {
    const activeStatus = isPolling && pollingData
      ? pollingData.generation_status
      : data?.generation_status;

    if (activeStatus === 'failed' && !hasCompleted && !hasCompletedRef.current) {
      handleCompletion(isPolling && pollingData ? pollingData : data!);
    }
  }, [data?.generation_status, pollingData?.generation_status, hasCompleted, isPolling, pollingData]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (dismissTimerRef.current) {
        clearTimeout(dismissTimerRef.current);
      }
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Determine status - use polling data if available
  const activeData = isPolling && pollingData ? pollingData : data;
  const isFailed = activeData?.generation_status === 'failed' || error;
  const isAt100Percent = activeData?.progress === 100 || hasCompleted;
  const isConnecting = !activeData && !error && !hasCompleted && !isPolling;
  const showLiveIndicator = isConnected && !hasCompleted && !isDisconnected && !isPolling;

  // Render toast with data
  return (
    <motion.div
      className={`${styles.toast} ${isAt100Percent ? styles.complete : ''} ${isFailed ? styles.failed : ''}`}
      initial={{ opacity: 0, x: 100, y: -20 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      exit={{ opacity: 0, x: 100, y: -20 }}
      transition={{ duration: 0.3, ease: 'easeOut' }}
    >
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={`${styles.liveDot} ${isAt100Percent ? styles.completeDot : ''}`}>
            {isAt100Percent || hasCompleted ? '' : isConnecting ? '○' : '●'}
          </span>
          <span className={styles.title}>
            {isConnecting ? 'STARTING GENERATION...' : isAt100Percent || hasCompleted ? 'COURSE READY' : isFailed ? 'GENERATION FAILED' : isPolling ? 'COURSE GENERATING (POLLING)' : 'COURSE GENERATING'}
          </span>
        </div>
        <div className={styles.headerActions}>
          <button
            className={styles.expandBtn}
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? 'Collapse' : 'Expand'}
            type="button"
            disabled={isConnecting || hasCompleted}
          >
            {isExpanded ? '−' : '+'}
          </button>
          <button
            className={styles.dismissBtn}
            onClick={onDismiss}
            title="Dismiss"
            type="button"
          >
            ×
          </button>
        </div>
      </div>

      <div className={styles.content}>
        {isConnecting ? (
          <>
            <h3 className={styles.topic}>Initializing course generation...</h3>
            <div className={styles.loadingBar}>
              <motion.div
                className={styles.loadingFill}
                animate={{ x: ['-100%', '100%'] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
              />
            </div>
            <div style={{ marginTop: '12px', fontFamily: 'var(--font-mono)', fontSize: '10px', color: '#666' }}>
              {isConnected ? ' Connected to stream' : connectionAttempts > 0 ? `Connecting... (attempt ${connectionAttempts})` : 'Establishing connection...'}
            </div>
          </>
        ) : (
          <>
            <h3 className={styles.topic}>{activeData?.topic || (hasCompleted ? 'Course Generation Complete!' : 'Loading...')}</h3>

            {!isFailed && activeData && (
              <>
                <div className={styles.stage}>
                  {activeData.current_stage || (hasCompleted ? 'All tasks completed' : isPolling ? 'Polling for updates...' : 'Preparing course...')}
                </div>

                <div className={styles.progressSection}>
                  <div className={styles.progressHeader}>
                    <span>PROGRESS</span>
                    <span className={styles.percentage}>{activeData.progress || (hasCompleted ? 100 : 0)}%</span>
                  </div>
                  <div className={styles.progressBar}>
                    <motion.div
                      className={styles.progressFill}
                      initial={{ width: 0 }}
                      animate={{ width: `${activeData?.progress || (hasCompleted ? 100 : 0)}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                  <div className={styles.progressFooter}>
                    {activeData.total_days && activeData.total_days > 0 && (() => {
                      // Use total_days directly from backend (already includes days + tests calculation)
                      const totalDayTasks = activeData.total_days;
                      const totalWeeks = Math.ceil(totalDayTasks / 5);
                      const totalTestTasks = totalWeeks * 2;
                      return (
                        <span>
                          {activeData.completed_days || 0} / {totalDayTasks} days + {totalTestTasks} tests
                        </span>
                      );
                    })()}
                    <span className={`${styles.status} ${isAt100Percent ? styles.statusComplete : ''}`}>
                      {isAt100Percent || hasCompleted ? ' READY' : activeData.generation_status || 'generating'}
                    </span>
                  </div>
                </div>

                {/* Connection indicator - only show when actively connecting/generating */}
                {!hasCompleted && !isDisconnected && !isPolling && (
                  <div style={{ marginTop: '8px', fontFamily: 'var(--font-mono)', fontSize: '9px', color: isConnected ? '#00aa00' : '#ff8800' }}>
                    {isConnected ? '● Live updates' : '○ Reconnecting...'}
                  </div>
                )}
                
                {/* Show polling indicator */}
                {isPolling && !hasCompleted && (
                  <div style={{ marginTop: '8px', fontFamily: 'var(--font-mono)', fontSize: '9px', color: '#ff8800' }}>
                    ● Polling for updates...
                  </div>
                )}

                {/* Show completion message instead of connection status */}
                {hasCompleted && (
                  <div style={{ marginTop: '8px', fontFamily: 'var(--font-mono)', fontSize: '9px', color: '#00aa00' }}>
                     Course generation complete! Dismissing shortly...
                  </div>
                )}
              </>
            )}

            {error && (
              <div className={styles.errorBox}>
                <span className={styles.errorIcon}></span>
                <span className={styles.errorMessage}>{error}</span>
              </div>
            )}

            {isExpanded && activeData?.weeks && (
              <motion.div
                className={styles.weeksSection}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
              >
                <div className={styles.weeksLabel}>WEEK BREAKDOWN</div>
                <div className={styles.weeksGrid}>
                  {activeData.weeks.map((week: any) => (
                    <div key={week.week} className={`${styles.weekCell} ${styles[week.status]}`}>
                      <span className={styles.weekLabel}>W{week.week}</span>
                      <div className={styles.weekDays}>
                        {week.days?.map((day: any) => (
                          <span
                            key={day.day}
                            className={`${styles.dayDot} ${styles[day.status]}`}
                            title={day.title}
                          />
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </>
        )}
      </div>
    </motion.div>
  );
}
