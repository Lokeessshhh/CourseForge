'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import Link from 'next/link';
import styles from './GeneratingCourseCard.module.css';

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
  course: GeneratingCourse;
  onDismiss: (id: string) => void;
}

export default function GeneratingCourseCard({ course, onDismiss }: Props) {
  const [localProgress, setLocalProgress] = useState(course.progress);

  useEffect(() => {
    setLocalProgress(course.progress);
  }, [course.progress]);

  // Don't show if completed or failed
  if (course.generation_status === 'ready' || course.generation_status === 'failed') {
    return null;
  }

  return (
    <motion.div
      className={styles.card}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.4 }}
    >
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <span className={styles.liveIndicator}>●</span>
          <span className={styles.title}>GENERATING COURSE</span>
        </div>
        <button
          className={styles.dismissBtn}
          onClick={() => onDismiss(course.id)}
          title="Dismiss (course will continue generating)"
        >
          ×
        </button>
      </div>

      <div className={styles.content}>
        <h3 className={styles.courseTopic}>{course.topic}</h3>

        <div className={styles.stageBadge}>
          {course.current_stage}
        </div>

        <div className={styles.progressContainer}>
          <div className={styles.progressLabel}>
            <span>GENERATION PROGRESS</span>
            <span>{localProgress}%</span>
          </div>
          <div className={styles.progressBar}>
            <motion.div
              className={styles.progressFill}
              initial={{ width: 0 }}
              animate={{ width: `${localProgress}%` }}
              transition={{ duration: 0.5 }}
            />
          </div>
          <div className={styles.progressDetails}>
            {(() => {
              const totalWeeks = Math.round(course.total_days / 7);
              const totalDayTasks = totalWeeks * 5;
              const totalTestTasks = totalWeeks * 2;
              return (
                <span>{course.completed_days} / {totalDayTasks} days + {totalTestTasks} tests completed</span>
              );
            })()}
            <span className={styles.status}>{course.generation_status.toUpperCase()}</span>
          </div>
        </div>

        <div className={styles.footer}>
          <Link
            href={`/dashboard/generate?id=${course.id}`}
            className={styles.viewButton}
          >
            VIEW PROGRESS →
          </Link>
        </div>
      </div>
    </motion.div>
  );
}
