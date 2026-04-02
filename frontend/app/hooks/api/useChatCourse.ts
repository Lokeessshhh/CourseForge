'use client';

import { useApiClient } from '@/app/hooks/useApiClient';
import { useState, useCallback } from 'react';

// Types
export interface ChatCourseRequest {
  message?: string;
  confirmation?: boolean;
  crud_enabled?: boolean;  // Enable LLM-based CRUD routing
  session_id?: string;  // Chat session ID
  form_data?: {
    course_name?: string;
    duration_weeks?: number;
    level?: 'beginner' | 'intermediate' | 'advanced';
    description?: string;
    confirm_delete?: boolean;  // For delete confirmation
    [key: string]: any;  // Allow additional fields
  };
}

export interface ChatCourseResponse {
  success?: boolean;
  data?: {
    // New simplified command-based fields
    command?: 'create_course' | 'delete_course' | 'read_course' | 'read_day' | 'answer_mcq' | 'list_courses' | 'show_course' | 'chat' | 'week_day_summary' | 'update_course';
    action?: 'call_delete_api' | 'call_create_api' | 'show_confirmation' | 'show_form' | 'just_respond' | 'confirm' | 'deleted' | 'create' | 'list' | 'show' | 'respond' | 'show_options' | 'execute_update' | 'show_llm_summary' | 'error';
    response?: string;
    course_id?: string;
    course_name?: string;
    course_data?: {
      course_name: string;
      duration_weeks: number;
      level: string;
      description?: string;
    };
    course?: {
      id: string;
      course_name: string;
      level: string;
      duration_weeks: number;
      progress: number;
      status: string;
    };
    courses?: Array<{
      id: string;
      course_name: string;
      level: string;
      duration_weeks: number;
      progress: number;
    }>;
    missing_fields?: string[];
    prefilled?: Record<string, any>;
    // Update course fields
    update_options?: Array<{
      type: '50%' | '75%' | 'extend_50%';
      label: string;
      description: string;
      duration_change: string;
    }>;
    user_query?: string;
    update_type?: string;
    // Legacy LLM-based fields (for backward compatibility)
    intent?: 'create_course' | 'delete_course' | 'read_course' | 'read_day' | 'answer_mcq' | 'list_courses' | 'chat';
    confidence?: number;
    entities?: Record<string, any>;
    matched_course_name?: string;
    week_number?: number;
    day_number?: number;
    question_number?: number;
    summary?: string;
    summary_type?: 'day' | 'week' | 'course' | null;
  };
  // Top-level fields (for backward compatibility)
  command?: 'create_course' | 'delete_course' | 'read_course' | 'read_day' | 'answer_mcq' | 'list_courses' | 'show_course' | 'chat';
  action?: 'call_delete_api' | 'call_create_api' | 'show_confirmation' | 'show_form' | 'just_respond' | 'confirm' | 'deleted' | 'create' | 'list' | 'show' | 'respond';
  intent?: 'create_course' | 'delete_course' | 'read_course' | 'read_day' | 'answer_mcq' | 'list_courses' | 'chat';
  confidence?: number;
  entities?: Record<string, any>;
  response?: string;
  course_id?: string;
  course_name?: string;
  matched_course_name?: string;
  course_data?: {
    course_name: string;
    duration_weeks: number;
    level: string;
    description?: string;
  };
  course?: {
    id: string;
    course_name: string;
    level: string;
    duration_weeks: number;
    progress: number;
    status: string;
  };
  courses?: Array<{
    id: string;
    course_name: string;
    level: string;
    duration_weeks: number;
    progress: number;
  }>;
  missing_fields?: string[];
  prefilled?: Record<string, any>;
  week_number?: number;
  day_number?: number;
  question_number?: number;
  summary?: string;
  summary_type?: 'day' | 'week' | 'course' | null;
  user_query?: string;
  update_options?: Array<{
    type: '50%' | '75%' | 'extend_50%';
    label: string;
    description: string;
    duration_change: string;
  }>;
  update_type?: string;
}

export interface DayContent {
  status: 'ready' | 'not_ready';
  course_name: string;
  week_number: number;
  day_number: number;
  day_title: string;
  theory_content: string;
  code_content: string;
  quizzes: any[];
  tasks: any;
  message?: string;
}

export interface MCQContent {
  course_name: string;
  week_number: number;
  day_number: number;
  questions: Array<{
    id: string;
    question_number: number;
    question_text: string;
    options: Record<string, string>;
    correct_answer: string;
    explanation: string;
  }>;
}

interface UseChatCourseState {
  isLoading: boolean;
  error: string | null;
}

export function useChatCourse() {
  const api = useApiClient();
  const [state, setState] = useState<UseChatCourseState>({
    isLoading: false,
    error: null,
  });

  const sendChatMessage = useCallback(async (
    data: ChatCourseRequest
  ): Promise<ChatCourseResponse | null> => {
    setState({ isLoading: true, error: null });
    try {
      const result = await api.post<ChatCourseResponse>('/api/chat/', data);
      return result;
    } catch (err) {
      setState({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to send message',
      });
      return null;
    } finally {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, [api]);

  const createCourse = useCallback(async (
    courseData: {
      course_name: string;
      duration_weeks: number;
      level: 'beginner' | 'intermediate' | 'advanced';
      description?: string;
      session_id?: string;  // Add session_id
    }
  ) => {
    setState({ isLoading: true, error: null });
    try {
      const result = await api.post('/api/chat/create/', courseData);
      return result;
    } catch (err) {
      setState({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to create course',
      });
      return null;
    } finally {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, [api]);

  const deleteCourse = useCallback(async (courseId: string) => {
    setState({ isLoading: true, error: null });
    try {
      const result = await api.post('/api/chat/delete/', { course_id: courseId });
      return result;
    } catch (err) {
      setState({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to delete course',
      });
      return null;
    } finally {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, [api]);

  const getDayContent = useCallback(async (
    courseId: string,
    weekNumber: number,
    dayNumber: number
  ): Promise<DayContent | null> => {
    setState({ isLoading: true, error: null });
    try {
      const result = await api.get<DayContent>(
        `/api/chat/course/${courseId}/week/${weekNumber}/day/${dayNumber}/`
      );
      return result;
    } catch (err) {
      setState({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to get day content',
      });
      return null;
    } finally {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, [api]);

  const getMCQContent = useCallback(async (
    courseId: string,
    weekNumber: number,
    dayNumber: number,
    questionNumber?: number
  ): Promise<MCQContent | null> => {
    setState({ isLoading: true, error: null });
    try {
      const url = questionNumber
        ? `/api/chat/course/${courseId}/week/${weekNumber}/day/${dayNumber}/mcq/${questionNumber}/`
        : `/api/chat/course/${courseId}/week/${weekNumber}/day/${dayNumber}/mcq/`;
      const result = await api.get<MCQContent>(url);
      return result;
    } catch (err) {
      setState({
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to get MCQ content',
      });
      return null;
    } finally {
      setState(prev => ({ ...prev, isLoading: false }));
    }
  }, [api]);

  return {
    ...state,
    sendChatMessage,
    createCourse,
    deleteCourse,
    getDayContent,
    getMCQContent,
  };
}
