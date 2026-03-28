import { api } from '@/app/lib/api';
import { useState, useEffect, useCallback } from 'react';

// Types
export interface Certificate {
  id: string;
  course_id: string;
  course_name: string;
  student_name: string;
  final_score: number;
  avg_test_score: number;
  total_study_hours: number;
  total_days: number;
  completion_date: string;
  days_taken: number;
  certificate_id: string;
  download_url: string | null;
  share_url: string;
  is_unlocked: boolean;
  status: string | null;
}

// API Functions
export const certificateApi = {
  getCertificate: (courseId: string) =>
    api.get<Certificate>(`/api/courses/${courseId}/certificate/`),

  generateCertificate: (courseId: string) =>
    api.post<Certificate>(`/api/courses/${courseId}/certificate/generate/`),
};

// Hook
export function useCertificate(courseId: string) {
  const [data, setData] = useState<Certificate | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCertificate = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await certificateApi.getCertificate(courseId);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [courseId]);

  useEffect(() => {
    fetchCertificate();
  }, [fetchCertificate]);

  const generate = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await certificateApi.generateCertificate(courseId);
      setData(result);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [courseId]);

  return { data, isLoading, error, refetch: fetchCertificate, generate };
}
