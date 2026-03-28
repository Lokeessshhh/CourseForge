'use client';

import { useApiClient } from '@/app/hooks/useApiClient';
import { useState, useEffect, useCallback } from 'react';

// Types
export interface UserProgress {
  total_days_completed: number;
  courses_active: number;
  courses_completed: number;
  longest_streak: number;
  current_streak: number;
  avg_quiz_score: number;
  avg_test_score: number;
  total_study_hours: number;
}

export interface CourseProgressDetail {
  course_id: string;
  course_name: string;
  topic: string;
  progress: number;
  weeks: {
    week: number;
    completed_days: number;
    total_days: number;
    test_score: number | null;
  }[];
}

export interface ConceptMastery {
  concept: string;
  mastery: number;
  practiced_count: number;
  last_practiced: string | null;
}

export interface QuizHistoryItem {
  date: string;
  course: string;
  day: string;
  score: number;
  passed: boolean;
}

export interface StreakCalendar {
  weeks: boolean[][];
}

export interface FullProgress {
  overall: UserProgress;
  courses: CourseProgressDetail[];
  concepts: ConceptMastery[];
  quiz_history: QuizHistoryItem[];
  streak_calendar: StreakCalendar;
}

// Hook
export function useUserProgress() {
  const api = useApiClient();
  const [data, setData] = useState<FullProgress | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await api.get<FullProgress>('/api/users/me/progress/');
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, isLoading, error, refetch: fetchData };
}

export function useCourseProgressDetail(courseId: string) {
  const api = useApiClient();
  const [data, setData] = useState<CourseProgressDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await api.get<CourseProgressDetail>(`/api/courses/${courseId}/progress/`);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [courseId, api]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, isLoading, error, refetch: fetchData };
}
