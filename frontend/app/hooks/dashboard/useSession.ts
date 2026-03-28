import { useState, useEffect, useCallback } from 'react';

interface Session {
  id: string;
  title: string;
  courseId?: string;
  courseName?: string;
  messageCount: number;
  lastMessageAt: Date;
  createdAt: Date;
}

interface UseSessionOptions {
  courseId?: string;
}

export function useSession({ courseId }: UseSessionOptions = {}) {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSessions = useCallback(async () => {
    try {
      const url = courseId
        ? `${process.env.NEXT_PUBLIC_API_URL}/chat/sessions/?course_id=${courseId}`
        : `${process.env.NEXT_PUBLIC_API_URL}/chat/sessions/`;
      
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error('Failed to fetch sessions');
      }
      
      const data = await response.json();
      setSessions(data.sessions || data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const createSession = useCallback(async (title?: string, contextCourseId?: string) => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/chat/sessions/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title || 'New Chat',
          course_id: contextCourseId || courseId,
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to create session');
      }
      
      const newSession = await response.json();
      setSessions((prev) => [newSession, ...prev]);
      setCurrentSession(newSession);
      return newSession;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, [courseId]);

  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/chat/sessions/${sessionId}/`,
        { method: 'DELETE' }
      );
      
      if (!response.ok) {
        throw new Error('Failed to delete session');
      }
      
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      
      if (currentSession?.id === sessionId) {
        setCurrentSession(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  }, [currentSession]);

  const selectSession = useCallback((session: Session) => {
    setCurrentSession(session);
  }, []);

  return {
    sessions,
    currentSession,
    isLoading,
    error,
    createSession,
    deleteSession,
    selectSession,
    refetch: fetchSessions,
  };
}
