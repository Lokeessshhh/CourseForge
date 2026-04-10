'use client';

import { useEffect } from 'react';
import { useGenerationProgress as useStringProgress } from '@/app/components/GenerationProgressProvider/GenerationProgressProvider';
import { useGenerationProgress as useMapProgress } from '@/app/context/GenerationProgressContext';

/**
 * Bridges the String-based progress context (used by pages)
 * with the Map-based context (used by the toast).
 * When a page calls startGeneration(), this ensures the course
 * is added to the Map so the toast can display it.
 */
export default function GenerationProgressBridge() {
  const { generatingCourseId } = useStringProgress();
  const { addGeneratingCourse } = useMapProgress();

  useEffect(() => {
    if (generatingCourseId) {
      addGeneratingCourse({
        courseId: generatingCourseId,
        courseName: '',
        progress: 0,
        completed_days: 0,
        total_days: 0,
        generation_status: 'generating',
        current_stage: 'Starting generation...',
      });
    }
  }, [generatingCourseId, addGeneratingCourse]);

  return null;
}
