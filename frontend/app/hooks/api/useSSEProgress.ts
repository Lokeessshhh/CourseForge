'use client';

import { useEffect, useRef, useCallback, useState } from 'react';

/**
 * Server-Sent Events (SSE) hook for course generation progress.
 * Provides real-time updates from backend.
 * 
 * @param courseId - Course ID to monitor
 * @param enabled - Whether to connect (default: true)
 * @returns Current progress data and connection state
 */
export interface SSEProgressData {
  progress: number;
  completed_days: number;
  total_days: number;
  generation_status: 'pending' | 'generating' | 'ready' | 'failed' | 'updating';
  current_stage?: string;
  weeks?: any[];
  topic?: string;
}

export interface UseSSEProgressResult {
  data: SSEProgressData | null;
  isConnected: boolean;
  isComplete: boolean;
  error: string | null;
  reconnect: () => void;
  disconnect: () => void;
}

export function useSSEProgress(
  courseId: string | null,
  enabled: boolean = true
): UseSSEProgressResult {
  const [data, setData] = useState<SSEProgressData | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ref to track if we've received the complete event (even if data state hasn't updated yet)
  const completeEventReceivedRef = useRef(false);
  // Ref to track pending complete data that arrived with the complete event
  const pendingCompleteDataRef = useRef<SSEProgressData | null>(null);
  // Timeout ref for grace period handling
  const errorGracePeriodTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 2000; // 2 seconds

  // Cleanup function
  const cleanup = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (errorGracePeriodTimeoutRef.current) {
      clearTimeout(errorGracePeriodTimeoutRef.current);
      errorGracePeriodTimeoutRef.current = null;
    }
  }, []);

  // Connect to SSE stream
  const connect = useCallback(() => {
    if (!courseId || !enabled) {
      return;
    }

    // Reset completion refs for new course
    completeEventReceivedRef.current = false;
    pendingCompleteDataRef.current = null;

    // Close existing connection
    cleanup();

    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const url = `${baseUrl}/api/courses/${courseId}/progress/sse/`;

    console.log('[SSE] Connecting to:', url);

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    // Connection opened
    eventSource.addEventListener('connected', (event) => {
      console.log('[SSE] ✅ Connected:', event.data);
      setIsConnected(true);
      setError(null);
      reconnectAttemptsRef.current = 0;
    });

    // Progress updates
    eventSource.addEventListener('progress', (event) => {
      try {
        const progressData: SSEProgressData = JSON.parse(event.data);
        console.log('[SSE] 📊 Progress update:', progressData);
        setData(progressData);
        
        // Check if complete
        if (progressData.generation_status === 'ready' || 
            progressData.generation_status === 'failed') {
          setIsComplete(true);
        }
      } catch (err) {
        console.error('[SSE] Failed to parse progress data:', err);
      }
    });

    // Generation complete - THIS IS THE CRITICAL FIX
    eventSource.addEventListener('complete', (event) => {
      try {
        const progressData: SSEProgressData = JSON.parse(event.data);
        console.log('[SSE] ✅✅✅ GENERATION COMPLETE EVENT RECEIVED:', progressData);

        // Set refs immediately (before state updates) to prevent race condition
        completeEventReceivedRef.current = true;
        pendingCompleteDataRef.current = progressData;

        // Update state
        setData(progressData);
        setIsComplete(true);
        setError(null); // Clear any pending errors
        
        // DO NOT close connection here - let toast component handle dismissal after 3 seconds
        // The toast will call disconnect() when it's ready to dismiss
        console.log('[SSE] ⏳ Keeping connection open for toast 3-second display...');

      } catch (err) {
        console.error('[SSE] Failed to parse complete data:', err);
      }
    });

    // Heartbeat
    eventSource.addEventListener('heartbeat', (event) => {
      const heartbeat = JSON.parse(event.data);
      console.log('[SSE] 💓 Heartbeat:', heartbeat);
    });

    // Error handling - BULLETPROOF VERSION WITH GRACE PERIOD
    eventSource.addEventListener('error', (event: any) => {
      console.log('[SSE] Error event received:', event);

      // CRITICAL: Check refs first (they're set synchronously before state updates)
      const justCompleted = completeEventReceivedRef.current || 
                           pendingCompleteDataRef.current?.generation_status === 'ready';
      
      // Also check state
      const stateIsComplete = isComplete || 
                             data?.generation_status === 'ready' || 
                             data?.generation_status === 'failed';

      // If we just completed, this is a NORMAL connection close - ignore it
      if (justCompleted || stateIsComplete) {
        console.log('[SSE] ✅ Generation complete - error event is normal connection close');
        setIsConnected(false);
        cleanup();
        return;
      }

      // SSE error events may not have data
      if (event.data) {
        try {
          const errorData = JSON.parse(event.data);
          
          // Check if this error event actually contains complete data
          if (errorData.generation_status === 'ready') {
            console.log('[SSE] ✅ Error event contains complete data, processing as complete');
            completeEventReceivedRef.current = true;
            pendingCompleteDataRef.current = errorData;
            setData(errorData);
            setIsComplete(true);
            setError(null);
            cleanup();
            return;
          }
          
          // Real error with data
          setError(errorData.error || 'SSE connection error');
        } catch {
          setError('SSE connection error');
        }
      } else {
        // No data in error event - this is usually a normal connection close
        // BUT we add a 500ms grace period to see if a complete event arrives
        
        console.log('[SSE] ⏳ Error event has no data, starting 500ms grace period...');
        
        // Clear any existing grace period timeout
        if (errorGracePeriodTimeoutRef.current) {
          clearTimeout(errorGracePeriodTimeoutRef.current);
        }
        
        // Wait 500ms to see if complete event arrives
        errorGracePeriodTimeoutRef.current = setTimeout(() => {
          // After grace period, check again if we completed
          const completedNow = completeEventReceivedRef.current || 
                              pendingCompleteDataRef.current?.generation_status === 'ready' ||
                              isComplete ||
                              data?.generation_status === 'ready';
          
          if (completedNow) {
            console.log('[SSE] ✅ Grace period: Generation completed during wait, ignoring error');
            setError(null);
          } else {
            // Still not complete after grace period - this is a real connection loss
            console.log('[SSE] ❌ Grace period: Still not complete, setting connection lost error');
            setError('Connection lost');
          }
          
          errorGracePeriodTimeoutRef.current = null;
        }, 500);
        
        // Don't set error yet - wait for grace period
        return;
      }

      setIsConnected(false);

      // Don't auto-reconnect on generation complete
      const status = data?.generation_status as SSEProgressData['generation_status'] | undefined;
      if (status === 'ready' ||
          status === 'failed' ||
          isComplete ||
          completeEventReceivedRef.current) {
        cleanup();
        return;
      }

      // Attempt reconnection
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        reconnectAttemptsRef.current += 1;
        console.log(`[SSE] Reconnecting in ${reconnectDelay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);
        reconnectTimeoutRef.current = setTimeout(connect, reconnectDelay);
      } else {
        console.error('[SSE] Max reconnection attempts reached');
        setError('Connection lost - please refresh the page');
      }
    });

    // Native open event
    eventSource.onopen = () => {
      console.log('[SSE] 🔓 Connection opened');
    };

    // Native error event (fallback) - BULLETPROOF VERSION
    eventSource.onerror = (err) => {
      // Check refs first (synchronous)
      const justCompleted = completeEventReceivedRef.current || 
                           pendingCompleteDataRef.current?.generation_status === 'ready';
      
      // Check state
      const stateIsComplete = isComplete || 
                             data?.generation_status === 'ready' || 
                             data?.generation_status === 'failed';

      if (justCompleted || stateIsComplete) {
        console.log('[SSE] ✅ Native error: Generation complete, ignoring');
        return;
      }

      // Only log, don't show error if we might be complete
      console.log('[SSE] Native error event (not complete yet):', err);
      
      if (!isConnected && !justCompleted && !stateIsComplete) {
        setError('Failed to connect to progress stream');
      }
    };

  }, [courseId, enabled, cleanup, data?.generation_status, isComplete]);

  // Manual reconnect
  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect]);

  // Manual disconnect
  const disconnect = useCallback(() => {
    console.log('[SSE] 🔌 Manual disconnect');
    cleanup();
  }, [cleanup]);

  // Auto-connect on mount and when courseId changes
  useEffect(() => {
    if (enabled && courseId) {
      connect();
    }
    
    // Cleanup on unmount
    return () => {
      console.log('[SSE] 🧹 Cleanup');
      cleanup();
    };
  }, [courseId, enabled, connect, cleanup]);

  return {
    data,
    isConnected,
    isComplete,
    error,
    reconnect,
    disconnect,
  };
}
