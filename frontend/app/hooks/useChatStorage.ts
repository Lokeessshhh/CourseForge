'use client';

import { useCallback, useEffect } from 'react';

const STORAGE_KEYS = {
  CURRENT_SESSION_ID: 'chat_currentSessionId',
  SESSION_MESSAGES: 'chat_messages_',
  SESSIONS_LIST: 'chat_sessions_',
  PREFIX: 'chat_',
} as const;

interface StoredMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  sessionId?: string;
  // Progress placeholder message properties
  isProgressPlaceholder?: boolean;
  courseId?: string;
  isUpdateProgress?: boolean;  // Distinguish update progress from generation progress
}

interface StoredSession {
  id: string;
  title: string;
  course_id?: string | null;
  generatingCourseIds?: string[];  // Track generating courses for this session
  created_at: string;
  updated_at: string;
}

/**
 * LocalStorage hook for persisting chat sessions and messages.
 * Ensures chat state survives page navigation and refreshes.
 */
export function useChatStorage() {
  /**
   * Save current session ID to localStorage
   */
  const saveCurrentSessionId = useCallback((sessionId: string | null) => {
    if (typeof window === 'undefined') return;
    
    if (sessionId) {
      localStorage.setItem(STORAGE_KEYS.CURRENT_SESSION_ID, sessionId);
    } else {
      localStorage.removeItem(STORAGE_KEYS.CURRENT_SESSION_ID);
    }
  }, []);

  /**
   * Get current session ID from localStorage
   */
  const getCurrentSessionId = useCallback((): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(STORAGE_KEYS.CURRENT_SESSION_ID);
  }, []);

  /**
   * Save messages for a session to localStorage
   */
  const saveSessionMessages = useCallback((sessionId: string, messages: StoredMessage[]) => {
    if (typeof window === 'undefined') return;
    
    try {
      const key = `${STORAGE_KEYS.SESSION_MESSAGES}${sessionId}`;
      localStorage.setItem(key, JSON.stringify(messages));
    } catch (e) {
      console.error('Failed to save session messages to localStorage:', e);
    }
  }, []);

  /**
   * Get messages for a session from localStorage
   */
  const getSessionMessages = useCallback((sessionId: string): StoredMessage[] | null => {
    if (typeof window === 'undefined') return null;
    
    try {
      const key = `${STORAGE_KEYS.SESSION_MESSAGES}${sessionId}`;
      const data = localStorage.getItem(key);
      if (!data) return null;
      return JSON.parse(data);
    } catch (e) {
      console.error('Failed to get session messages from localStorage:', e);
      return null;
    }
  }, []);

  /**
   * Save session metadata to localStorage
   */
  const saveSession = useCallback((session: StoredSession) => {
    if (typeof window === 'undefined') return;
    
    try {
      const key = `${STORAGE_KEYS.SESSIONS_LIST}${session.id}`;
      localStorage.setItem(key, JSON.stringify(session));
      
      // Also update sessions list
      const sessionsListKey = `${STORAGE_KEYS.PREFIX}sessionsList`;
      const existingList = localStorage.getItem(sessionsListKey);
      let sessionsList: string[] = existingList ? JSON.parse(existingList) : [];
      
      if (!sessionsList.includes(session.id)) {
        sessionsList.push(session.id);
        localStorage.setItem(sessionsListKey, JSON.stringify(sessionsList));
      }
    } catch (e) {
      console.error('Failed to save session to localStorage:', e);
    }
  }, []);

  /**
   * Add generating course ID to a session
   */
  const addGeneratingCourseToSession = useCallback((sessionId: string, courseId: string) => {
    if (typeof window === 'undefined') return;
    
    try {
      const key = `${STORAGE_KEYS.SESSIONS_LIST}${sessionId}`;
      const data = localStorage.getItem(key);
      const session: StoredSession = data ? JSON.parse(data) : {
        id: sessionId,
        title: 'Chat',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      
      if (!session.generatingCourseIds) {
        session.generatingCourseIds = [];
      }
      
      if (!session.generatingCourseIds.includes(courseId)) {
        session.generatingCourseIds.push(courseId);
      }
      
      session.updated_at = new Date().toISOString();
      localStorage.setItem(key, JSON.stringify(session));
    } catch (e) {
      console.error('Failed to add generating course to session:', e);
    }
  }, []);

  /**
   * Remove generating course ID from a session
   */
  const removeGeneratingCourseFromSession = useCallback((sessionId: string, courseId: string) => {
    if (typeof window === 'undefined') return;
    
    try {
      const key = `${STORAGE_KEYS.SESSIONS_LIST}${sessionId}`;
      const data = localStorage.getItem(key);
      if (!data) return;
      
      const session: StoredSession = JSON.parse(data);
      if (session.generatingCourseIds) {
        session.generatingCourseIds = session.generatingCourseIds.filter(id => id !== courseId);
      }
      
      session.updated_at = new Date().toISOString();
      localStorage.setItem(key, JSON.stringify(session));
    } catch (e) {
      console.error('Failed to remove generating course from session:', e);
    }
  }, []);

  /**
   * Get generating course IDs for a session
   */
  const getSessionGeneratingCourseIds = useCallback((sessionId: string): string[] => {
    if (typeof window === 'undefined') return [];
    
    try {
      const key = `${STORAGE_KEYS.SESSIONS_LIST}${sessionId}`;
      const data = localStorage.getItem(key);
      if (!data) return [];
      
      const session: StoredSession = JSON.parse(data);
      return session.generatingCourseIds || [];
    } catch (e) {
      console.error('Failed to get generating course IDs from session:', e);
      return [];
    }
  }, []);

  /**
   * Get session metadata from localStorage
   */
  const getSession = useCallback((sessionId: string): StoredSession | null => {
    if (typeof window === 'undefined') return null;
    
    try {
      const key = `${STORAGE_KEYS.SESSIONS_LIST}${sessionId}`;
      const data = localStorage.getItem(key);
      if (!data) return null;
      return JSON.parse(data);
    } catch (e) {
      console.error('Failed to get session from localStorage:', e);
      return null;
    }
  }, []);

  /**
   * Get all session IDs from localStorage
   */
  const getAllSessionIds = useCallback((): string[] => {
    if (typeof window === 'undefined') return [];
    
    try {
      const sessionsListKey = `${STORAGE_KEYS.PREFIX}sessionsList`;
      const data = localStorage.getItem(sessionsListKey);
      if (!data) return [];
      return JSON.parse(data);
    } catch (e) {
      console.error('Failed to get sessions list from localStorage:', e);
      return [];
    }
  }, []);

  /**
   * Clear all chat-related localStorage data
   */
  const clearAllChatStorage = useCallback(() => {
    if (typeof window === 'undefined') return;
    
    try {
      const keys = Object.keys(localStorage).filter(key => 
        key.startsWith(STORAGE_KEYS.PREFIX)
      );
      keys.forEach(key => localStorage.removeItem(key));
    } catch (e) {
      console.error('Failed to clear chat storage:', e);
    }
  }, []);

  /**
   * Clear old sessions (keep only last N sessions)
   */
  const clearOldSessions = useCallback((keepCount: number = 10) => {
    if (typeof window === 'undefined') return;
    
    try {
      const sessionsListKey = `${STORAGE_KEYS.PREFIX}sessionsList`;
      const data = localStorage.getItem(sessionsListKey);
      if (!data) return;
      
      const sessionsList: string[] = JSON.parse(data);
      if (sessionsList.length <= keepCount) return;
      
      // Remove old sessions
      const sessionsToRemove = sessionsList.slice(0, sessionsList.length - keepCount);
      sessionsToRemove.forEach(sessionId => {
        localStorage.removeItem(`${STORAGE_KEYS.SESSIONS_LIST}${sessionId}`);
        localStorage.removeItem(`${STORAGE_KEYS.SESSION_MESSAGES}${sessionId}`);
      });
      
      // Update list
      localStorage.setItem(sessionsListKey, JSON.stringify(sessionsList.slice(-keepCount)));
    } catch (e) {
      console.error('Failed to clear old sessions:', e);
    }
  }, []);

  return {
    saveCurrentSessionId,
    getCurrentSessionId,
    saveSessionMessages,
    getSessionMessages,
    saveSession,
    getSession,
    getAllSessionIds,
    clearAllChatStorage,
    clearOldSessions,
    addGeneratingCourseToSession,
    removeGeneratingCourseFromSession,
    getSessionGeneratingCourseIds,
  };
}

/**
 * HOC-style wrapper to auto-save/restore chat state
 */
export function useChatPersistence(
  currentSessionId: string | null,
  messages: any[],
  onSessionRestore?: (sessionId: string, messages: any[]) => void
) {
  const storage = useChatStorage();

  // Save on unmount or when session/messages change
  useEffect(() => {
    return () => {
      if (currentSessionId) {
        storage.saveCurrentSessionId(currentSessionId);
        storage.saveSessionMessages(currentSessionId, messages);
      }
    };
  }, [currentSessionId, messages, storage]);

  // Restore on mount
  useEffect(() => {
    const savedSessionId = storage.getCurrentSessionId();
    if (savedSessionId) {
      const savedMessages = storage.getSessionMessages(savedSessionId);
      if (savedMessages && onSessionRestore) {
        onSessionRestore(savedSessionId, savedMessages);
      }
    }
  }, [storage, onSessionRestore]);

  return storage;
}
