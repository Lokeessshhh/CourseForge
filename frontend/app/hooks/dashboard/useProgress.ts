import { useState, useEffect, useCallback } from 'react';

interface CourseProgress {
  courseId: string;
  courseName: string;
  topic: string;
  totalWeeks: number;
  currentWeek: number;
  currentDay: number;
  totalDays: number;
  completedDays: number;
  progress: number;
  weekProgress: {
    week: number;
    completedDays: number;
    totalDays: number;
    testCompleted: boolean;
    testScore?: number;
  }[];
}

interface OverallProgress {
  totalCourses: number;
  activeCourses: number;
  completedCourses: number;
  totalDaysCompleted: number;
  totalStudyHours: number;
  currentStreak: number;
  longestStreak: number;
  avgQuizScore: number;
  avgTestScore: number;
}

interface ConceptMastery {
  concept: string;
  mastery: number;
  practicedCount: number;
  lastPracticed: Date | null;
}

export function useProgress() {
  const [overallProgress, setOverallProgress] = useState<OverallProgress | null>(null);
  const [courseProgress, setCourseProgress] = useState<CourseProgress[]>([]);
  const [conceptMastery, setConceptMastery] = useState<ConceptMastery[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProgress = useCallback(async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/progress/`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch progress');
      }
      
      const data = await response.json();
      setOverallProgress(data.overall);
      setCourseProgress(data.courses);
      setConceptMastery(data.concepts);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProgress();
  }, [fetchProgress]);

  const updateConceptMastery = useCallback(async (concept: string, score: number) => {
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/progress/concepts/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ concept, score }),
      });
      
      // Refetch to get updated data
      fetchProgress();
    } catch (err) {
      console.error('Failed to update concept mastery:', err);
    }
  }, [fetchProgress]);

  return {
    overallProgress,
    courseProgress,
    conceptMastery,
    isLoading,
    error,
    refetch: fetchProgress,
    updateConceptMastery,
  };
}
