'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@clerk/nextjs';
import { WS_URL, api } from '@/app/lib/api';

const DEBUG_CHAT_WS = true;
function wsLog(event: string, data?: unknown) {
  if (!DEBUG_CHAT_WS) return;
  // eslint-disable-next-line no-console
  console.log(`[chat-ws] ${event}`, data ?? '');
}

// Types
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: { title: string; page?: number | null }[];
  timestamp: Date;
  date?: string;
  // Progress placeholder message properties
  isProgressPlaceholder?: boolean;
  courseId?: string;
  isUpdateProgress?: boolean;  // Distinguish update progress from generation progress
}

export interface ChatSession {
  id: string;
  title: string;
  course_id: string | null;
  message_count: number;
  last_message_at: string;
  created_at: string;
  date?: string;
}

export interface WebSearchResult {
  title: string;
  url: string;
  snippet: string;
  source?: string;
}

export interface WebSearchState {
  isActive: boolean;
  query: string;
  results: WebSearchResult[];
  success: boolean;
  messageId: string | null;
}

// WebSocket Chat Hook
export function useChat(courseId?: string, sessionId?: string) {
  const { getToken } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wsSessionId, setWsSessionId] = useState<string | null>(null);
  const [isSessionSwitching, setIsSessionSwitching] = useState(false);
  const [onTitleUpdated, setOnTitleUpdated] = useState<((sessionId: string, title: string) => void) | null>(null);
  const [webSearchState, setWebSearchState] = useState<WebSearchState>({
    isActive: false,
    query: '',
    results: [],
    success: false,
    messageId: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const currentMessageId = useRef<string | null>(null);
  const currentContent = useRef<string>('');
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isUnmountedRef = useRef(false);
  const isConnectingRef = useRef(false);
  const pendingSendsRef = useRef<Array<{ content: string; sessionId?: string }>>([]);
  const connectionSeqRef = useRef(0);
  const activeUrlRef = useRef<string | null>(null);
  const getTokenRef = useRef(getToken);
  const reconnectAttemptsRef = useRef(0);
  const lastSessionIdRef = useRef<string | null>(null);
  // Refs for current context - updated by separate effect
  const sessionIdRef = useRef<string | null>(sessionId || null);
  const courseIdRef = useRef<string | undefined>(courseId);

  // Keep refs in sync
  getTokenRef.current = getToken;
  sessionIdRef.current = sessionId || null;
  courseIdRef.current = courseId;

  const connect = useCallback(async () => {
    try {
      const token = await getTokenRef.current();
      if (isUnmountedRef.current) return; // Check again after async

      if (!token) {
        setError('Authentication service unavailable');
        isConnectingRef.current = false;
        return;
      }

      // Use refs to get current values
      const currentCourseId = courseIdRef.current;
      const currentSessionId = sessionIdRef.current;

      const wsUrl = currentCourseId
        ? `${WS_URL}/ws/chat/${currentCourseId}/?token=${token}&session_id=${currentSessionId || ''}`
        : `${WS_URL}/ws/chat/?token=${token}&session_id=${currentSessionId || ''}`;

      // PREVENT CHURN: If URL is exactly the same and we're already connecting/connected, bail.
      if (activeUrlRef.current === wsUrl && (isConnectingRef.current || (wsRef.current && wsRef.current.readyState <= 1))) {
        wsLog('connect:skipping_duplicate', { wsUrl: wsUrl.replace(token, '[token]') });
        console.log('[WS] WARNING: Skipping duplicate connection - already connected');
        return;
      }

      // Don't reconnect if session hasn't changed and we're still connected
      if (lastSessionIdRef.current === currentSessionId && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsLog('connect:skipping_already_connected', { sessionId: currentSessionId });
        console.log('[WS] SUCCESS: Already connected, skipping');
        return;
      }

      console.log('[WS] CONNECTING: Attempting WebSocket connection...');
      console.log('[WS] URL:', wsUrl.replace(token, '[TOKEN]'));
      console.log('[WS] Session ID:', currentSessionId || 'none');
      console.log('[WS] Course ID:', currentCourseId || 'none (global chat)');

      isConnectingRef.current = true;
      activeUrlRef.current = wsUrl;
      lastSessionIdRef.current = currentSessionId || null;
      connectionSeqRef.current += 1;
      const seq = connectionSeqRef.current;
      wsLog('connect:start', { seq, courseId: currentCourseId, sessionId: currentSessionId });

      // Clear any pending reconnect since we are actively connecting now
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      // Close existing connection if any
      if (wsRef.current) {
        wsLog('connect:closing_existing', { seq, readyState: wsRef.current.readyState });
        wsRef.current.close();
        wsRef.current = null;
      }

      wsLog('connect:url', { seq, wsUrl: wsUrl.replace(token, '[token]') });

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      
      // Capture current sequence number for this WebSocket instance
      const wsSeq = wsInstanceSeqRef.current;
      wsLog('ws:created', { seq, wsSeq });

      ws.onopen = () => {
        if (isUnmountedRef.current) {
          ws.close();
          return;
        }
        isConnectingRef.current = false;
        setIsConnected(true);
        setError(null);
        reconnectAttemptsRef.current = 0; // Reset on successful connection
        wsLog('ws:onopen', { seq });

        // Flush any queued sends (e.g., first message sent during reconnect)
        const queued = pendingSendsRef.current;
        pendingSendsRef.current = [];
        wsLog('send:flush_queue', { seq, queued: queued.length });
        for (const item of queued) {
          try {
            ws.send(JSON.stringify({
              message: item.content,
              message_id: crypto.randomUUID(),
              include_sources: true,
              session_id: item.sessionId,
            }));
            wsLog('send:flushed', { seq, sessionId: item.sessionId, preview: item.content.slice(0, 80) });
          } catch (e) {
            // If send fails, re-queue and break to avoid dropping messages
            pendingSendsRef.current.unshift(item);
            wsLog('send:flush_failed_requeued', { seq, error: String(e) });
            break;
          }
        }
      };

      ws.onmessage = (event) => {
        if (isUnmountedRef.current) return;
        
        // Ignore messages if this WebSocket is no longer the current one
        if (wsRef.current !== ws) {
          wsLog('ws:onmessage:ignored:stale_ws', { seq, wsSeq });
          return;
        }
        
        // Also check sequence number to handle session changes
        if (wsSeq !== wsInstanceSeqRef.current) {
          wsLog('ws:onmessage:ignored:stale_seq', { seq, wsSeq, currentSeq: wsInstanceSeqRef.current });
          return;
        }

        const data = JSON.parse(event.data);
        wsLog('ws:onmessage', { seq, type: data?.type, message_id: data?.message_id, session_id: data?.session_id });

        switch (data.type) {
          case 'connected':
            // Connection confirmed with session info
            setWsSessionId(data.session_id);
            wsLog('ws:connected', { seq, wsSessionId: data.session_id });
            break;

          case 'thinking':
            setIsThinking(true);
            break;

          case 'cache_hit':
            // Cache hit - response will be streamed from cache
            break;

          case 'stream_start':
            setIsThinking(true);
            currentMessageId.current = data.message_id;
            currentContent.current = '';
            wsLog('stream:start', { seq, message_id: data.message_id });
            console.log('[useChat] stream_start - adding message:', data.message_id);
            setMessages(prev => {
              console.log('[useChat] stream_start - prev messages count:', prev.length);
              const newMessages = [
                ...prev,
                {
                  id: data.message_id,
                  role: 'assistant' as const,
                  content: '',
                  sources: [],
                  timestamp: new Date(),
                },
              ];
              console.log('[useChat] stream_start - new messages count:', newMessages.length);
              return newMessages;
            });
            break;

          case 'stream_token':
            currentContent.current += data.token;
            if (currentContent.current.length < 10) {
              wsLog('stream:token', { seq, message_id: data.message_id });
            }
            setMessages(prev =>
              prev.map(msg =>
                msg.id === currentMessageId.current
                  ? { ...msg, content: currentContent.current }
                  : msg
              )
            );
            break;

          case 'stream_end':
            setIsThinking(false);
            wsLog('stream:end', { seq, message_id: data.message_id, sources: (data.sources || []).length });
            setMessages(prev =>
              prev.map(msg =>
                msg.id === currentMessageId.current
                  ? { ...msg, sources: data.sources || [] }
                  : msg
              )
            );
            currentMessageId.current = null;
            currentContent.current = '';
            break;

          case 'title_updated':
            // Handle title update from backend
            wsLog('ws:title_updated', { seq, session_id: data.session_id, title: data.title });
            if (onTitleUpdated && data.session_id && data.title) {
              onTitleUpdated(data.session_id, data.title);
            }
            break;

          case 'web_search_start':
            // Web search started
            setWebSearchState({
              isActive: true,
              query: data.query || '',
              results: [],
              success: false,
              messageId: data.message_id || null,
            });
            wsLog('ws:web_search_start', { seq, message_id: data.message_id, query: data.query });
            break;

          case 'web_search_end':
            // Web search completed
            setWebSearchState({
              isActive: false,
              query: data.query || '',
              results: data.results || [],
              success: data.success || false,
              messageId: data.message_id || null,
            });
            wsLog('ws:web_search_end', { seq, message_id: data.message_id, success: data.success, results: (data.results || []).length });
            break;

          case 'ping':
            // Ignore ping messages (heartbeat from server)
            wsLog('ws:ping', { seq });
            break;

          case 'error':
            setError(data.message);
            setIsThinking(false);
            wsLog('ws:error_message', { seq, message: data.message, message_id: data.message_id });
            break;
        }
      };

      ws.onerror = () => {
        if (isUnmountedRef.current) return;
        setError('WebSocket error');
        setIsConnected(false);
        setIsThinking(false);
        isConnectingRef.current = false;
        wsLog('ws:onerror', { seq });
      };

      ws.onclose = () => {
        if (isUnmountedRef.current) return;
        setIsConnected(false);
        setIsThinking(false);
        isConnectingRef.current = false;
        activeUrlRef.current = null;
        wsLog('ws:onclose', { seq, readyState: ws.readyState, queued: pendingSendsRef.current.length });
        
        // Auto reconnect after delay with exponential backoff (max 30 seconds)
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
        
        // Only reconnect if we haven't exceeded max attempts
        const maxReconnectAttempts = 10;
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          reconnectAttemptsRef.current += 1;
          wsLog('reconnect:scheduled', { seq, attempt: reconnectAttemptsRef.current, delay });
          
          reconnectTimeoutRef.current = setTimeout(() => {
            if (!isUnmountedRef.current && !isConnectingRef.current) {
              wsLog('reconnect:timer_fired', { seq, attempt: reconnectAttemptsRef.current });
              connect();
            }
          }, delay);
        } else {
          wsLog('reconnect:max_attempts_reached', { seq });
          setError('Connection lost. Please refresh the page.');
        }
      };
    } catch (err) {
      if (isUnmountedRef.current) return;
      setError(err instanceof Error ? err.message : 'Connection failed');
      isConnectingRef.current = false;
      const seq = connectionSeqRef.current;
      wsLog('connect:exception', { seq, error: String(err) });
    }
  }, []); // Empty deps - uses refs for current values

  const prevSessionIdRef = useRef<string | null>(null);
  const hasInitializedRef = useRef(false);
  const wsInstanceSeqRef = useRef(0); // Track current WebSocket instance

  // Update refs when values change - DON'T clear messages here anymore
  useEffect(() => {
    const oldSessionId = sessionIdRef.current;
    const sessionIdChanged = oldSessionId !== sessionId && hasInitializedRef.current;
    
    // Update refs AFTER checking for change
    sessionIdRef.current = sessionId || null;
    courseIdRef.current = courseId;
    hasInitializedRef.current = true;

    if (sessionIdChanged) {
      wsLog('session:changed', { oldSession: oldSessionId, newSession: sessionId });

      // Set session switching state
      setIsSessionSwitching(true);
      
      // Ensure switching state is visible for at least 300ms
      setTimeout(() => {
        setIsSessionSwitching(false);
      }, 300);

      // Increment sequence to invalidate old WebSocket's message handlers
      wsInstanceSeqRef.current += 1;
      console.log('[useChat] Session changed, incremented wsInstanceSeq to:', wsInstanceSeqRef.current);

      // Close the old WebSocket to force reconnect with new session
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsLog('session:closing_for_reconnect', { sessionId });
        wsRef.current.close();
      }
      // NOTE: Messages are now cleared in handleSend before session change
    }
  }, [sessionId, courseId]);

  // Main connection effect - connects when component mounts or when WebSocket is closed
  useEffect(() => {
    isUnmountedRef.current = false;
    
    // Only connect if we have a sessionId or we're in global mode
    if (sessionIdRef.current || !courseIdRef.current) {
      wsLog('effect:connecting', { courseId: courseIdRef.current, sessionId: sessionIdRef.current });
      connect();
    }

    return () => {
      isUnmountedRef.current = true;
      wsLog('effect:cleanup_unmount', { courseId: courseIdRef.current, sessionId: sessionIdRef.current });

      // Clear reconnect timeout
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      // Close WebSocket on unmount only
      if (wsRef.current) {
        wsLog('cleanup:closing_ws', { readyState: wsRef.current.readyState });
        wsRef.current.close();
        wsRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Empty deps - connection managed internally

  const send = useCallback((content: string, outgoingSessionId?: string, webSearch?: boolean, ragEnabled?: boolean) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      // Queue the send to be flushed on next open. This prevents losing the first
      // message during session switches/reconnect churn.
      pendingSendsRef.current.push({ content, sessionId: outgoingSessionId });
      wsLog('send:queued', { sessionId: outgoingSessionId, queued: pendingSendsRef.current.length, preview: content.slice(0, 80) });
      // Trigger a reconnect attempt if we're not connected
      if (!isConnectingRef.current) {
        connect();
      }
      return true;
    }

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);

    ws.send(JSON.stringify({
      message: content,
      message_id: crypto.randomUUID(),
      include_sources: true,
      session_id: outgoingSessionId,
      web_search: webSearch || false,
      rag_enabled: ragEnabled || false,
    }));

    wsLog('send:sent', { sessionId: outgoingSessionId, webSearch, ragEnabled, preview: content.slice(0, 80) });

    return true;
  }, [connect]);

  const clearMessages = useCallback(() => {
    console.log('[useChat] clearMessages called');
    setMessages([]);
  }, []);

  const setMessagesExternal = useCallback((newMessages: ChatMessage[]) => {
    console.log('[useChat] setMessagesExternal called, count:', newMessages.length);
    setMessages(newMessages);
  }, []);

  const reconnect = useCallback(() => {
    // Clear any pending reconnect timeout
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    reconnectAttemptsRef.current = 0;
    connect();
  }, [connect]);

  // Method to set title update callback
  const onTitleUpdate = useCallback((callback: (sessionId: string, title: string) => void) => {
    setOnTitleUpdated(() => callback);
  }, []);

  return {
    messages,
    isConnected,
    isThinking,
    isSessionSwitching,
    error,
    send,
    clearMessages,
    setMessages: setMessagesExternal,
    reconnect,
    onTitleUpdate,
    webSearchState,
    clearWebSearch: () => {
      setWebSearchState({
        isActive: false,
        query: '',
        results: [],
        success: false,
        messageId: null,
      });
    },
  };
}

// Chat Sessions Hook
export const chatSessionsApi = {
  getSessions: () =>
    api.get<ChatSession[]>('/api/conversations/'),

  createSession: (data?: { course_id?: string; title?: string }) =>
    api.post<{ session_id: string; course_id: string | null; title: string; created_at: string }>('/api/conversations/sessions/new/', data || {}),

  getSessionHistory: (sessionId: string) =>
    api.get<{ session: { session_id: string; course_id: string | null; title: string; message_count: number; created_at: string; updated_at: string }; messages: any[] }>(`/api/conversations/sessions/${sessionId}/`),

  deleteSession: (sessionId: string) =>
    api.delete(`/api/conversations/sessions/${sessionId}/delete/`),

  renameSession: (sessionId: string, title: string) =>
    api.patch<{ session_id: string; title: string }>(`/api/conversations/sessions/${sessionId}/rename/`, { title }),

  archiveSession: (sessionId: string, archived: boolean = true) =>
    api.patch<{ session_id: string; archived: boolean }>(`/api/conversations/sessions/${sessionId}/archive/`, { archived }),

  getSessionTitle: (sessionId: string) =>
    api.get<{ session_id: string; title: string }>(`/api/conversations/sessions/${sessionId}/title/get/`),
};

export function useChatSessions() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSessions = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await chatSessionsApi.getSessions();
      setSessions(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const createSession = useCallback(async (data?: { course_id?: string; title?: string }) => {
    try {
      const result = await chatSessionsApi.createSession(data);
      await fetchSessions();
      return result.session_id;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, [fetchSessions]);

  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      await chatSessionsApi.deleteSession(sessionId);
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    }
  }, []);

  const renameSession = useCallback(async (sessionId: string, title: string) => {
    try {
      await chatSessionsApi.renameSession(sessionId, title);
      setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, title } : s));
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    }
  }, []);

  const archiveSession = useCallback(async (sessionId: string, archived: boolean = true) => {
    try {
      await chatSessionsApi.archiveSession(sessionId, archived);
      // Optionally filter out archived sessions from the list
      if (archived) {
        setSessions(prev => prev.filter(s => s.id !== sessionId));
      }
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    }
  }, []);

  return { sessions, isLoading, error, refetch: fetchSessions, createSession, deleteSession, renameSession, archiveSession };
}

export function useChatHistory(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    if (!sessionId) {
      // Clear messages when no session is selected
      setMessages([]);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const result = await chatSessionsApi.getSessionHistory(sessionId);
      setMessages(result.messages.map((m: any) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        timestamp: new Date(m.created_at),
        date: m.date,
        sources: [],
      })));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return { messages, isLoading, error, refetch: fetchHistory };
}

// Hook to poll for session title updates
export function useSessionTitlePoll(sessionId: string, onTitleUpdate?: (title: string) => void) {
  const [isPolling, setIsPolling] = useState(false);
  const pollTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const pollTitle = useCallback(async () => {
    if (!sessionId) return;
    try {
      const result = await chatSessionsApi.getSessionTitle(sessionId);
      if (result.title && result.title !== '[Session created]' && result.title !== 'New Chat') {
        onTitleUpdate?.(result.title);
        setIsPolling(false);
        return;
      }
      // Continue polling if title is still placeholder
      pollTimeoutRef.current = setTimeout(pollTitle, 2000);
    } catch (err) {
      wsLog('poll_title:error', err);
      setIsPolling(false);
    }
  }, [sessionId, onTitleUpdate]);

  const startPolling = useCallback(() => {
    if (!isPolling) {
      setIsPolling(true);
      pollTitle();
    }
  }, [isPolling, pollTitle]);

  const stopPolling = useCallback(() => {
    setIsPolling(false);
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return { isPolling, startPolling, stopPolling };
}
