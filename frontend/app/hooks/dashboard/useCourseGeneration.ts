import { useState, useEffect, useCallback } from 'react';

interface CourseStatus {
  id: string;
  topic: string;
  status: 'pending' | 'generating' | 'completed' | 'failed';
  progress: number;
  totalDays: number;
  completedDays: number;
  weeks: {
    week: number;
    status: 'pending' | 'generating' | 'completed';
    days: {
      day: number;
      title: string;
      status: 'pending' | 'generating' | 'completed';
    }[];
  }[];
}

interface UseCourseGenerationOptions {
  courseId: string;
  pollInterval?: number;
}

export function useCourseGeneration({ courseId, pollInterval = 3000 }: UseCourseGenerationOptions) {
  const [status, setStatus] = useState<CourseStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/courses/${courseId}/generation-status/`
      );
      
      if (!response.ok) {
        throw new Error('Failed to fetch course status');
      }
      
      const data = await response.json();
      setStatus(data);
      setError(null);
      
      // Stop polling if completed or failed
      if (data.status === 'completed' || data.status === 'failed') {
        return false;
      }
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    let intervalId: NodeJS.Timeout;
    let shouldContinue = true;

    const poll = async () => {
      if (shouldContinue) {
        shouldContinue = await fetchStatus();
      }
    };

    poll();

    intervalId = setInterval(() => {
      if (shouldContinue) {
        poll();
      } else {
        clearInterval(intervalId);
      }
    }, pollInterval);

    return () => {
      clearInterval(intervalId);
    };
  }, [fetchStatus, pollInterval]);

  const startGeneration = useCallback(async (params: {
    topic: string;
    duration: string;
    skillLevel: string;
  }) => {
    setIsLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/courses/generate/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });
      
      if (!response.ok) {
        throw new Error('Failed to start course generation');
      }
      
      const data = await response.json();
      setStatus(data);
      return data.id;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    }
  }, []);

  return { status, isLoading, error, startGeneration, refetch: fetchStatus };
}
