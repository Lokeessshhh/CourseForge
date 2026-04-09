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
  // New generation progress fields
  current_stage?: string;
  generation_status?: string;
}

export interface GenerateCourseData {
  course_name: string;
  duration_weeks: number;
  level: 'beginner' | 'intermediate' | 'advanced';
  goals?: string[];
  hours_per_day?: number;
  description?: string;  // Optional user-provided description
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
        // Use the new generation-progress endpoint for real-time updates
        const data: any = await api.get(`/api/courses/${id}/generation-progress/`);
        
        // Map the response to match CourseStatus interface
        const mappedData: CourseStatus = {
          id,
          topic: data.data?.topic || '',
          status: data.data?.status === 'ready' ? 'completed' : data.data?.status === 'failed' ? 'failed' : 'generating',
          progress: data.data?.progress || 0,
          total_days: data.data?.total_days || 0,
          completed_days: data.data?.completed_days || 0,
          current_stage: data.data?.current_stage,
          generation_status: data.data?.generation_status,
          weeks: data.data?.weeks || [], // Use weeks from backend
        };
        
        setStatus(mappedData);
        setError(null);
        setIsLoading(false);

        // Stop polling if completed or failed
        if (data.data?.status === 'ready' || data.data?.status === 'failed') {
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
      const data: any = await api.get(`/api/courses/${id}/generation-progress/`);
      const mappedData: CourseStatus = {
        id,
        topic: data.data?.topic || '',
        status: data.data?.status === 'ready' ? 'completed' : data.data?.status === 'failed' ? 'failed' : 'generating',
        progress: data.data?.progress || 0,
        total_days: data.data?.total_days || 0,
        completed_days: data.data?.completed_days || 0,
        current_stage: data.data?.current_stage,
        generation_status: data.data?.generation_status,
        weeks: data.data?.weeks || [],
      };
      setStatus(mappedData);
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
      await api.delete(`/api/courses/${id}/delete/`);
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

export interface UpdateCoursePreview {
  course_id: string;
  course_name: string;
  current_duration_weeks: number;
  new_duration_weeks: number;
  update_type: string;
  weeks_to_update: number[];
  weeks_to_preserve: number[];
  total_days_affected: number;
  estimated_new_days: number;
  requires_confirmation: boolean;
  user_query?: string;
}

export interface UpdateCourseData {
  update_type: 'percentage' | 'extend' | 'compact';
  user_query: string;
  web_search_enabled?: boolean;
  percentage?: 50 | 75;
  extend_weeks?: number;
  target_weeks?: number;
}

export function useUpdateCourse() {
  const api = useApiClient();
  const [isUpdating, setIsUpdating] = useState(false);
  const [isFetchingPreview, setIsFetchingPreview] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<UpdateCoursePreview | null>(null);

  const getUpdatePreview = useCallback(async (courseId: string, data: UpdateCourseData) => {
    setIsFetchingPreview(true);
    setError(null);
    try {
      const result = await api.post<UpdateCoursePreview>(`/api/courses/${courseId}/update-preview/`, data);
      setPreview(result);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setIsFetchingPreview(false);
    }
  }, [api]);

  const updateCourse = useCallback(async (courseId: string, data: UpdateCourseData) => {
    setIsUpdating(true);
    setError(null);
    try {
      const result = await api.post<{
        course_id: string;
        status: string;
        weeks_to_update: number[];
        new_duration_weeks: number;
      }>(`/api/courses/${courseId}/update/`, data);
      return result;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      console.error('[useCourses] Update course error:', errorMessage, err);
      // Return error object with message for frontend to display
      return { error: errorMessage };
    } finally {
      setIsUpdating(false);
    }
  }, [api]);

  const clearPreview = useCallback(() => {
    setPreview(null);
  }, []);

  return { 
    updateCourse, 
    getUpdatePreview, 
    clearPreview,
    isUpdating, 
    isFetchingPreview, 
    error,
    preview 
  };
}
