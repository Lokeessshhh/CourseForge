'use client';

import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

export interface GeneratingCourse {
  courseId: string;
  courseName: string;
  progress: number;
  completed_days: number;
  total_days: number;
  generation_status: 'pending' | 'generating' | 'ready' | 'failed' | 'updating';
  current_stage?: string;
  topic?: string;
  startedAt: number;
  createdBySessionId?: string;  // Track which chat session created this course
}

interface GenerationProgressContextType {
  generatingCourses: Map<string, GeneratingCourse>;
  addGeneratingCourse: (course: Omit<GeneratingCourse, 'startedAt'>) => void;
  updateGeneratingCourse: (courseId: string, updates: Partial<GeneratingCourse>) => void;
  removeGeneratingCourse: (courseId: string) => void;
  getGeneratingCourse: (courseId: string) => GeneratingCourse | undefined;
  clearCompletedCourses: () => void;
}

const GenerationProgressContext = createContext<GenerationProgressContextType | undefined>(undefined);

export function GenerationProgressProvider({ children }: { children: ReactNode }) {
  const [generatingCourses, setGeneratingCourses] = useState<Map<string, GeneratingCourse>>(() => {
    // Initialize from localStorage on mount
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('generatingCourses');
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          // Convert array back to Map
          const map = new Map<string, GeneratingCourse>();
          // Handle both array and object formats
          if (Array.isArray(parsed)) {
            parsed.forEach((item: any) => {
              if (item.courseId) {
                map.set(item.courseId, item);
              }
            });
          } else if (parsed && typeof parsed === 'object') {
            // If it's already a Map-like object from previous save
            Object.entries(parsed).forEach(([key, value]: [string, any]) => {
              if (value.courseId) {
                map.set(key, value);
              }
            });
          }
          return map;
        } catch (e) {
          console.error('Failed to parse generating courses from localStorage:', e);
        }
      }
    }
    return new Map();
  });

  // Persist to localStorage whenever it changes
  useEffect(() => {
    if (typeof window !== 'undefined') {
      // Convert Map to array for localStorage
      const coursesArray = Array.from(generatingCourses.values());
      localStorage.setItem('generatingCourses', JSON.stringify(coursesArray));
    }
  }, [generatingCourses]);

  const addGeneratingCourse = useCallback((course: Omit<GeneratingCourse, 'startedAt'>) => {
    setGeneratingCourses(prev => {
      const newMap = new Map(prev);
      newMap.set(course.courseId, {
        ...course,
        startedAt: Date.now(),
      });
      return newMap;
    });
  }, []);

  const updateGeneratingCourse = useCallback((courseId: string, updates: Partial<GeneratingCourse>) => {
    setGeneratingCourses(prev => {
      const existing = prev.get(courseId);
      if (!existing) {
        return prev;
      }
      const newMap = new Map(prev);
      newMap.set(courseId, { ...existing, ...updates });
      return newMap;
    });
  }, []);

  const removeGeneratingCourse = useCallback((courseId: string) => {
    setGeneratingCourses(prev => {
      const newMap = new Map(prev);
      newMap.delete(courseId);
      return newMap;
    });
  }, []);

  const getGeneratingCourse = useCallback((courseId: string): GeneratingCourse | undefined => {
    return generatingCourses.get(courseId);
  }, [generatingCourses]);

  const clearCompletedCourses = useCallback(() => {
    setGeneratingCourses(prev => {
      const newMap = new Map(prev);
      for (const [key, course] of newMap.entries()) {
        if (course.generation_status === 'ready' || course.generation_status === 'failed') {
          newMap.delete(key);
        }
      }
      return newMap;
    });
  }, []);

  return (
    <GenerationProgressContext.Provider
      value={{
        generatingCourses,
        addGeneratingCourse,
        updateGeneratingCourse,
        removeGeneratingCourse,
        getGeneratingCourse,
        clearCompletedCourses,
      }}
    >
      {children}
    </GenerationProgressContext.Provider>
  );
}

export function useGenerationProgress() {
  const context = useContext(GenerationProgressContext);
  if (context === undefined) {
    throw new Error('useGenerationProgress must be used within a GenerationProgressProvider');
  }
  return context;
}
