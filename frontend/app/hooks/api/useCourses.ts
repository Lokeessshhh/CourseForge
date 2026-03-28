'use client';

import { useApiClient } from '@/app/hooks/useApiClient';
import { useState, useEffect, useCallback, useRef } from 'react';

// Types
export interface Course {
  id: string;
  course_name: string;
  topic: string;
  level: 'beginner' | 'intermediate' | 'advanced';
  duration_weeks: number;
  progress: number;
  current_week: number;
  current_day: number;
  hours_per_day: number;
  status: 'active' | 'completed' | 'paused';
  created_at: string;
  updated_at: string;
}

export interface CourseStatus {
  id: string;
  topic: string;
  status: 'pending' | 'generating' | 'completed' | 'failed';
  progress: number;
  total_days: number;
  completed_days: number;
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

export interface GenerateCourseData {
  course_name: string;
  duration_weeks: number;
  level: 'beginner' | 'intermediate' | 'advanced';
  goals?: string[];
  hours_per_day?: number;
}

export interface CourseProgress {
  course_id: string;
  course_name: string;
  topic: string;
  total_weeks: number;
  current_week: number;
  current_day: number;
  total_days: number;
  completed_days: number;
  progress: number;
  week_progress: {
    week: number;
    completed_days: number;
    total_days: number;
    test_completed: boolean;
    test_score?: number;
  }[];
}

interface UseApiState<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
}

function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
): UseApiState<T> & { refetch: () => void } {
  const [state, setState] = useState<UseApiState<T>>({
    data: null,
    isLoading: true,
    error: null,
  });

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const fetchData = useCallback(async () => {
    setState(prev => ({ ...prev, isLoading: true, error: null }));
    try {
      const data = await fetcherRef.current();
      setState({ data, isLoading: false, error: null });
    } catch (err) {
      setState({
        data: null,
        isLoading: false,
        error: err instanceof Error ? err.message : 'Unknown error',
      });
    }
  }, []);

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps]);

  return { ...state, refetch: fetchData };
}

export function useCourses() {
  const api = useApiClient();
  return useApi(() => api.get<Course[]>('/api/courses/'), []);
}

export function useCourse(id: string) {
  const api = useApiClient();
  return useApi(() => api.get<Course>(`/api/courses/${id}/`), [id]);
}

export function useCourseStatus(id: string, pollInterval = 0) {
  const api = useApiClient();
  const [status, setStatus] = useState<CourseStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;

    const fetchStatus = async () => {
      try {
        const data = await api.get<CourseStatus>(`/api/courses/${id}/status/`);
        setStatus(data);
        setError(null);
        setIsLoading(false);
        
        // Stop polling if completed or failed
        if (data.status === 'completed' || data.status === 'failed') {
          if (intervalId) clearInterval(intervalId);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        setIsLoading(false);
      }
    };

    fetchStatus();

    if (pollInterval > 0) {
      intervalId = setInterval(fetchStatus, pollInterval);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [id, pollInterval, api]);

  const refetch = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await api.get<CourseStatus>(`/api/courses/${id}/status/`);
      setStatus(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [id, api]);

  return { status, isLoading, error, refetch };
}

export function useGenerateCourse() {
  const api = useApiClient();
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = useCallback(async (data: GenerateCourseData) => {
    setIsGenerating(true);
    setError(null);
    try {
      const result = await api.post<{ id: string; status: string }>('/api/courses/generate/', data);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setIsGenerating(false);
    }
  }, [api]);

  return { generate, isGenerating, error };
}

export function useCourseProgress(id: string) {
  const api = useApiClient();
  return useApi(() => api.get<CourseProgress>(`/api/courses/${id}/progress/`), [id]);
}

export function useWeekPlans(courseId: string) {
  const api = useApiClient();
  return useApi(() => api.get<any[]>(`/api/courses/${courseId}/weeks/`), [courseId]);
}

export function useDayPlan(courseId: string, weekNumber: number, dayNumber: number) {
  const api = useApiClient();
  return useApi(
    () => api.get<any>(`/api/courses/${courseId}/weeks/${weekNumber}/days/${dayNumber}/`),
    [courseId, weekNumber, dayNumber]
  );
}

export function useDeleteCourse() {
  const api = useApiClient();
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deleteCourse = useCallback(async (id: string) => {
    setIsDeleting(true);
    setError(null);
    try {
      await api.delete(`/api/courses/${id}/`);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    } finally {
      setIsDeleting(false);
    }
  }, [api]);

  return { deleteCourse, isDeleting, error };
}
