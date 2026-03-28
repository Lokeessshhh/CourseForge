'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useUser } from '@clerk/nextjs';
import { useApiClient } from '@/app/hooks/useApiClient';
import Link from 'next/link';
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
}

function EmptyState() {
  const triggerCreate = () => {
    try {
      localStorage.setItem('dashboard:create_course', '1');
      window.dispatchEvent(new Event('dashboard:create_course'));
    } catch {
      // no-op
    }
  };

  return (
    <div className={styles.emptyBox}>
      <span className={styles.emptyText}>NO COURSES YET</span>
      <motion.button
        className={styles.createBtn}
        onClick={triggerCreate}
        whileHover={{ x: -2, y: -2 }}
        whileTap={{ scale: 0.98 }}
      >
        CREATE ONE →
      </motion.button>
    </div>
  );
}

export default function CoursesPage() {
  const { isLoaded } = useUser();
  const api = useApiClient();
  
  const [courses, setCourses] = useState<Course[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoaded) return;

    const fetchCourses = async () => {
      const startedAt = Date.now();
      setIsLoading(true);
      setError(null);
      try {
        const data = await api.get<Course[]>('/api/courses/');
        setCourses(data || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        const elapsed = Date.now() - startedAt;
        const remaining = 300 - elapsed;
        if (remaining > 0) {
          setTimeout(() => setIsLoading(false), remaining);
        } else {
          setIsLoading(false);
        }
      }
    };

    fetchCourses();
  }, [isLoaded, api]);

  if (!isLoaded) return null;

  return (
    <div className={styles.page}>
      <div className={styles.sectionLabel}>
        <span className={styles.labelIcon}>►</span>
        MY COURSES
      </div>

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
              <Link href={`/dashboard/courses/${course.id}`}>
                <motion.button
                  className={styles.courseRowBtn}
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                >
                  RESUME →
                </motion.button>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
