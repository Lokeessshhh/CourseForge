'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import styles from './GeneratingCourseWidget.module.css';

interface GeneratingCourse {
  id: string;
  topic: string;
  progress: number;
  completed_days: number;
  total_days: number;
  current_stage: string;
  generation_status: string;
}

interface Props {
  courseId: string;
  onDismiss: () => void;
  onRefresh?: () => void;
}

export default function GeneratingCourseWidget({ courseId, onDismiss, onRefresh }: Props) {
  const [course, setCourse] = useState<GeneratingCourse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!courseId) return;

    const fetchProgress = async () => {
      try {
        const response = await fetch(`/api/courses/${courseId}/generation-progress/`);
        if (!response.ok) throw new Error('Failed to fetch progress');
        const data = await response.json();

        if (data.success && data.data) {
          setCourse(data.data);
          setError(null);

          // Auto-dismiss and refresh dashboard if completed or failed
          if (data.data.generation_status === 'ready' || data.data.generation_status === 'failed') {
            // Refresh dashboard data first
            if (onRefresh) {
              onRefresh();
            }
            setTimeout(onDismiss, 2000);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load progress');
      }
    };

    // Initial fetch
    fetchProgress();

    // Poll every 3 seconds
    const interval = setInterval(fetchProgress, 3000);

    return () => clearInterval(interval);
  }, [courseId, onDismiss, onRefresh]);

  if (!course || course.generation_status === 'ready') {
    return null;
  }

  return (
    <motion.div
      className={styles.widget}
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
    >
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.liveDot}>●</span>
          <span className={styles.title}>COURSE GENERATING</span>
        </div>
        <button className={styles.dismissBtn} onClick={onDismiss} title="Dismiss">
          ×
        </button>
      </div>

      <div className={styles.content}>
        <h3 className={styles.topic}>{course.topic}</h3>

        <div className={styles.stage}>
          {course.current_stage}
        </div>

        <div className={styles.progressSection}>
          <div className={styles.progressHeader}>
            <span>PROGRESS</span>
            <span className={styles.percentage}>{course.progress}%</span>
          </div>
          <div className={styles.progressBar}>
            <motion.div
              className={styles.progressFill}
              initial={{ width: 0 }}
              animate={{ width: `${course.progress}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
          <div className={styles.progressFooter}>
            {(() => {
              const totalWeeks = Math.round(course.total_days / 7);
              const totalDayTasks = totalWeeks * 5;
              const totalTestTasks = totalWeeks * 2;
              return (
                <span>{course.completed_days} / {totalDayTasks} days + {totalTestTasks} tests</span>
              );
            })()}
            <span className={styles.status}>{course.generation_status}</span>
          </div>
        </div>

        <a href={`/dashboard/generate?id=${courseId}`} className={styles.viewLink}>
          View Full Progress →
        </a>
      </div>
    </motion.div>
  );
}
