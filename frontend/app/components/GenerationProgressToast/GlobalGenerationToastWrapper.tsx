'use client';

import { usePathname } from 'next/navigation';
import { useGenerationProgress } from '@/app/context/GenerationProgressContext';
import GenerationProgressToast from './GenerationProgressToast';

/**
 * GlobalGenerationToastWrapper
 * 
 * Shows toast notifications for all generating courses.
 * Reads from GenerationProgressContext to track courses across all pages.
 * DOES NOT show toast on chat page (in-chat progress bar is shown instead).
 */
export default function GlobalGenerationToastWrapper() {
  const pathname = usePathname();
  const { generatingCourses, removeGeneratingCourse } = useGenerationProgress();

  // Don't show toast on chat page (in-chat progress bar is shown instead)
  const isChatPage = pathname === '/dashboard/chat';

  if (isChatPage) {
    return null;
  }

  // Convert Map to array for rendering
  const courses = Array.from(generatingCourses.values());

  const handleDismiss = (courseId: string) => {
    removeGeneratingCourse(courseId);
  };

  const handleGenerationComplete = (courseId: string) => {
    // Keep the course in context briefly so user can navigate to it
    // Will be cleaned up by clearCompletedCourses after some time
  };

  return (
    <>
      {courses.map((course) => (
        <GenerationProgressToast
          key={course.courseId}
          courseId={course.courseId}
          onDismiss={() => handleDismiss(course.courseId)}
          onGenerationComplete={() => handleGenerationComplete(course.courseId)}
        />
      ))}
    </>
  );
}
