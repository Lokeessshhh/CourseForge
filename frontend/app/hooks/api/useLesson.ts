import { api } from '@/app/lib/api';
import { useState, useEffect, useCallback } from 'react';

// Types
export interface DayContent {
  id: string;
  day_number: number;
  title: string;
  theory_content: string;
  code_content: string;
  tasks: any;
  is_completed: boolean;
  is_locked: boolean;
  theory_generated: boolean;
  code_generated: boolean;
  quiz_generated: boolean;
}

export interface Quiz {
  id: string;
  day_id: string;
  questions: {
    id: number;
    question: string;
    options: string[];
    correct: number;
    explanation: string;
  }[];
}

export interface QuizResult {
  score: number;
  total: number;
  passed: boolean;
  answers: {
    question_id: number;
    selected: number;
    correct: number;
    is_correct: boolean;
  }[];
}

// API Functions
export const lessonApi = {
  getDay: (courseId: string, week: number, day: number) =>
    api.get<DayContent>(`/api/courses/${courseId}/weeks/${week}/days/${day}/`),

  startDay: (courseId: string, week: number, day: number) =>
    api.post<{ success: boolean }>(`/api/courses/${courseId}/weeks/${week}/days/${day}/start/`),

  completeDay: (courseId: string, week: number, day: number, score: number) =>
    api.post<{ success: boolean }>(
      `/api/courses/${courseId}/weeks/${week}/days/${day}/complete/`,
      { score }
    ),

  // Coding Test APIs
  getCodingTest: (courseId: string, week: number, testNumber: number = 1) =>
    api.get<any>(`/api/courses/${courseId}/weeks/${week}/coding-test/${testNumber}/`),

  startCodingTest: (courseId: string, week: number, testNumber: number = 1) =>
    api.post<{ attempt_id: string }>(`/api/courses/${courseId}/weeks/${week}/coding-test/${testNumber}/start/`),

  executeCodingChallenge: (courseId: string, week: number, attemptId: string, problemIndex: number, sourceCode: string, language: string, stdin: string, expectedOutput: string) =>
    api.post(`/api/courses/${courseId}/weeks/${week}/coding-test/execute/`, {
      attempt_id: attemptId,
      problem_index: problemIndex,
      source_code: sourceCode,
      language: language,
      stdin: stdin,
      expected_output: expectedOutput,
    }),

  submitCodingTest: (courseId: string, week: number, testNumber: number = 1, attemptId: string, challengeResults?: any[]) =>
    api.post<any>(`/api/courses/${courseId}/weeks/${week}/coding-test/${testNumber}/submit/`, {
      attempt_id: attemptId,
      challenge_results: challengeResults || [],
    }),
};

export const quizApi = {
  getQuiz: (courseId: string, week: number, day: number) =>
    api.get<Quiz>(`/api/courses/${courseId}/weeks/${week}/days/${day}/quiz/`),

  submitQuiz: (courseId: string, week: number, day: number, answers: number[]) => {
    // Convert array of indices to dict with question numbers as keys and letters as values
    const answersDict: Record<string, string> = {};
    answers.forEach((answerIndex, questionNum) => {
      // Convert 0-based index to letter (0->a, 1->b, 2->c, 3->d)
      const letter = String.fromCharCode(97 + answerIndex); // 97 is 'a'
      answersDict[String(questionNum + 1)] = letter; // 1-based question numbers
    });

    return api.post<QuizResult>(`/api/courses/${courseId}/weeks/${week}/days/${day}/quiz/submit/`, {
      answers: answersDict,
    });
  },

  getQuizResults: (courseId: string, week: number, day: number) =>
    api.get<QuizResult>(`/api/courses/${courseId}/weeks/${week}/days/${day}/quiz/results/`),

  getWeeklyTest: (courseId: string, week: number) =>
    api.get<Quiz>(`/api/courses/${courseId}/weeks/${week}/test/`),

  submitWeeklyTest: (courseId: string, week: number, answers: number[]) => {
    // Convert array of indices to dict with question numbers as keys and letters as values
    const answersDict: Record<string, string> = {};
    answers.forEach((answerIndex, questionNum) => {
      // Convert 0-based index to letter (0->a, 1->b, 2->c, 3->d)
      const letter = String.fromCharCode(97 + answerIndex); // 97 is 'a'
      answersDict[String(questionNum + 1)] = letter; // 1-based question numbers
    });

    return api.post<QuizResult>(`/api/courses/${courseId}/weeks/${week}/test/submit/`, {
      answers: answersDict,
    });
  },

  // Coding Test APIs
  getCodingTest: (courseId: string, week: number, testNumber: number = 1) =>
    api.get<any>(`/api/courses/${courseId}/weeks/${week}/coding-test/${testNumber}/`),

  startCodingTest: (courseId: string, week: number, testNumber: number = 1) =>
    api.post<{ attempt_id: string }>(`/api/courses/${courseId}/weeks/${week}/coding-test/${testNumber}/start/`),

  executeCodingChallenge: (courseId: string, week: number, attemptId: string, problemIndex: number, sourceCode: string, language: string, stdin: string, expectedOutput: string) =>
    api.post(`/api/courses/${courseId}/weeks/${week}/coding-test/execute/`, {
      attempt_id: attemptId,
      problem_index: problemIndex,
      source_code: sourceCode,
      language: language,
      stdin: stdin,
      expected_output: expectedOutput,
    }),

  submitCodingTest: (courseId: string, week: number, testNumber: number = 1, attemptId: string, challengeResults?: any[]) =>
    api.post<any>(`/api/courses/${courseId}/weeks/${week}/coding-test/${testNumber}/submit/`, {
      attempt_id: attemptId,
      challenge_results: challengeResults || [],
    }),
};

// Hooks
function useApiState<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
) {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, deps);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, isLoading, error, refetch: fetchData };
}

export function useDay(courseId: string, week: number, day: number) {
  return useApiState(
    () => lessonApi.getDay(courseId, week, day),
    [courseId, week, day]
  );
}

export function useQuiz(courseId: string, week: number, day: number) {
  return useApiState(
    () => quizApi.getQuiz(courseId, week, day),
    [courseId, week, day]
  );
}

export function useWeeklyTest(courseId: string, week: number) {
  return useApiState(
    () => quizApi.getWeeklyTest(courseId, week),
    [courseId, week]
  );
}

export function useLessonActions() {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const startDay = useCallback(async (courseId: string, week: number, day: number) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await lessonApi.startDay(courseId, week, day);
      return result.success;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return false;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const completeDay = useCallback(async (
    courseId: string, 
    week: number, 
    day: number, 
    score: number
  ) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await lessonApi.completeDay(courseId, week, day, score);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const submitQuiz = useCallback(async (
    courseId: string, 
    week: number, 
    day: number, 
    answers: number[]
  ) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await quizApi.submitQuiz(courseId, week, day, answers);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const submitWeeklyTest = useCallback(async (
    courseId: string, 
    week: number, 
    answers: number[]
  ) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await quizApi.submitWeeklyTest(courseId, week, answers);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  return {
    startDay,
    completeDay,
    submitQuiz,
    submitWeeklyTest,
    isSubmitting,
    error,
  };
}
