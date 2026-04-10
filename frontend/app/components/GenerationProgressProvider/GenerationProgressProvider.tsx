'use client';

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';

interface GenerationProgressContextType {
  generatingCourseId: string | null;
  isGenerating: boolean;
  startGeneration: (courseId: string) => void;
  completeGeneration: () => void;
  dismissGeneration: () => void;
}

const GenerationProgressContext = createContext<GenerationProgressContextType | undefined>(undefined);

export function GenerationProgressProvider({ children }: { children: ReactNode }) {
  const [generatingCourseId, setGeneratingCourseId] = useState<string | null>(null);

  const isGenerating = generatingCourseId !== null;

  const startGeneration = useCallback((courseId: string) => {
    console.log('[GenerationProgress] Starting generation for course:', courseId);
    setGeneratingCourseId(courseId);
  }, []);

  const completeGeneration = useCallback(() => {
    console.log('[GenerationProgress] Generation completed, clearing state');
    setGeneratingCourseId(null);
  }, []);

  const dismissGeneration = useCallback(() => {
    console.log('[GenerationProgress] Generation dismissed');
    setGeneratingCourseId(null);
  }, []);

  return (
    <GenerationProgressContext.Provider
      value={{
        generatingCourseId,
        isGenerating,
        startGeneration,
        completeGeneration,
        dismissGeneration,
      }}
    >
      {children}
    </GenerationProgressContext.Provider>
  );
}

export function useGenerationProgress() {
  const context = useContext(GenerationProgressContext);
  if (context === undefined) {
    throw new Error(
      'useGenerationProgress must be used within a GenerationProgressProvider'
    );
  }
  return context;
}
