'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useUser } from '@clerk/nextjs';
import { useApiClient } from '@/app/hooks/useApiClient';
import Link from 'next/link';
import { useGenerationProgress } from '@/app/components/GenerationProgressProvider/GenerationProgressProvider';
import styles from '../page.module.css';

interface Course {
  id: string;
  course_name: string;
  topic: string;
  level: string;
  duration_weeks: number;
  progress: number;
  current_week: number;
  current_day: number;
  status: string;
  generation_status?: string;
  generation_progress?: number;
  created_at: string;
}

function EmptyState() {
  return (
    <div className={styles.emptyBox}>
      <span className={styles.emptyText}>NO COURSES YET</span>
      <span className={styles.emptySubtext}>Use the input bar at the bottom to create a course</span>
    </div>
  );
}

export default function CoursesPage() {
  const { isLoaded } = useUser();
  const api = useApiClient();
  const { startGeneration, completeGeneration, generatingCourseId, isGenerating } = useGenerationProgress();

  const [courses, setCourses] = useState<Course[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Fetch courses and check for generating courses
  const fetchCourses = useCallback(async (checkGeneration = true) => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await api.get<Course[]>('/api/courses/');
      setCourses(data || []);

      if (checkGeneration) {
        // Check for generating courses
        const generatingCourses = (data || []).filter(
          c => c.generation_status === 'generating'
        );

        if (generatingCourses.length > 0) {
          // Start generation tracking for the first generating course
          if (!isGenerating || generatingCourseId !== generatingCourses[0].id) {
            console.log('[Courses] Found generating course:', generatingCourses[0].id);
            startGeneration(generatingCourses[0].id);
          }
        } else if (generatingCourses.length === 0 && isGenerating) {
          // No courses generating - clear the state
          console.log('[Courses] No generating courses, clearing state');
          completeGeneration();
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [api, isGenerating, generatingCourseId, startGeneration, completeGeneration]);

  // Initial fetch
  useEffect(() => {
    if (!isLoaded) return;
    fetchCourses(true);
  }, [isLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  // Continuous polling every 3 seconds to catch newly generating courses
  useEffect(() => {
    if (!isLoaded) return;

    console.log('[Courses] Starting continuous polling...');
    const pollInterval = setInterval(() => {
      fetchCourses(true);
    }, 3000);

    return () => clearInterval(pollInterval);
  }, [isLoaded, fetchCourses]);

  // Additional polling for course generation updates when actively generating
  useEffect(() => {
    if (!generatingCourseId) return;

    const generationPollInterval = setInterval(async () => {
      try {
        const data = await api.get<Course[]>('/api/courses/');
        const generatingCourses = (data || []).filter(
          c => c.generation_status === 'generating'
        );

        if (generatingCourses.length === 0) {
          // Generation complete
          completeGeneration();
          // Refresh courses list
          setCourses(data || []);
        }
      } catch (err) {
        console.error('[Courses] Generation polling error:', err);
      }
    }, 3000);

    return () => clearInterval(generationPollInterval);
  }, [generatingCourseId, api, completeGeneration]);

  const handleDeleteCourse = async (courseId: string, courseName: string) => {
    setDeletingId(courseId);
    try {
      await api.delete(`/api/courses/${courseId}/delete/`);
      setCourses(prev => prev.filter(c => c.id !== courseId));
      setDeleteConfirmId(null);
    } catch (err) {
      setError('Failed to delete course');
      console.error('Delete course error:', err);
    } finally {
      setDeletingId(null);
    }
  };

  if (!isLoaded) return null;

  return (
    <div className={styles.page}>
      <div className={styles.sectionLabel}>
        <span className={styles.labelIcon}>►</span>
        MY COURSES
      </div>

      {/* Delete Confirmation Modal */}
      {deleteConfirmId && (
        <div className={styles.modalOverlay}>
          <motion.div
            className={styles.modal}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.2 }}
          >
            <div className={styles.modalContent}>
              <h3 className={styles.modalTitle}>DELETE COURSE</h3>
              <p className={styles.modalText}>
                This will permanently delete all progress, quizzes, tests, and certificates.
              </p>
              <p className={styles.modalWarning}>This action cannot be undone.</p>
            </div>
            <div className={styles.modalActions}>
              <button
                className={styles.modalCancelBtn}
                onClick={() => setDeleteConfirmId(null)}
                disabled={deletingId === deleteConfirmId}
              >
                CANCEL
              </button>
              <button
                className={`${styles.modalDeleteBtn} ${deletingId === deleteConfirmId ? styles.deleting : ''}`}
                onClick={() => {
                  const course = courses.find(c => c.id === deleteConfirmId);
                  if (course) handleDeleteCourse(course.id, course.course_name);
                }}
                disabled={deletingId === deleteConfirmId}
              >
                {deletingId === deleteConfirmId ? 'DELETING...' : 'DELETE'}
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {courses.length === 0 ? (
        <EmptyState />
      ) : (
        <div className={styles.coursesList}>
          {courses.map((course, index) => (
            <motion.div
              key={course.id}
              className={styles.courseRow}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, delay: index * 0.1 }}
              whileHover={{ backgroundColor: 'var(--black)' }}
            >
              <div className={styles.courseRowContent}>
                <span className={styles.courseRowName}>{course.course_name}</span>
                <span className={styles.courseRowTopic}>{course.topic.length > 60 ? course.topic.slice(0, 60) + '...' : course.topic}</span>
              </div>
              <div className={styles.courseRowProgress}>
                <div className={styles.miniProgressBar}>
                  <motion.div
                    className={styles.miniProgressFill}
                    initial={{ width: 0 }}
                    animate={{ width: `${course.progress}%` }}
                    transition={{ duration: 0.6, delay: 0.2 + index * 0.1 }}
                  />
                </div>
                <span className={styles.courseRowPercent}>{course.progress}%</span>
              </div>
              <span className={styles.courseRowWeek}>WEEK {course.current_week}/{course.duration_weeks}</span>
              <div className={styles.courseRowActions}>
                <Link href={`/dashboard/courses/${course.id}`}>
                  <motion.button
                    className={styles.courseRowBtn}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    RESUME →
                  </motion.button>
                </Link>
                <motion.button
                  className={`${styles.deleteBtn} ${deletingId === course.id ? styles.deleting : ''}`}
                  onClick={() => setDeleteConfirmId(course.id)}
                  disabled={deletingId === course.id}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  title="Delete course"
                >
                  {deletingId === course.id ? 'DELETING...' : 'DELETE'}
                </motion.button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
