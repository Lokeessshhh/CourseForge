'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { useCourse, useCourseProgress, useWeekPlans } from '@/app/hooks/api';
import styles from './page.module.css';

function LoadingSkeleton() {
  return (
    <div className={styles.page}>
      <div className={styles.skeletonBox} style={{ width: '200px', height: '20px', marginBottom: '24px' }} />
      <div className={styles.layout}>
        <div className={styles.skeletonBox} style={{ width: '280px', height: '400px' }} />
        <div className={styles.skeletonBox} style={{ flex: 1, height: '400px' }} />
      </div>
    </div>
  );
}

function ErrorBox({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className={styles.page}>
      <div className={styles.errorBox}>
        <span className={styles.errorText}>✗ FAILED TO LOAD · {message}</span>
        <motion.button
          className={styles.retryBtn}
          onClick={onRetry}
          whileHover={{ x: -2, y: -2 }}
        >
          RETRY →
        </motion.button>
      </div>
    </div>
  );
}

export default function CoursePage() {
  const params = useParams();
  const courseId = params.id as string;

  const { data: course, isLoading: courseLoading, error: courseError, refetch: refetchCourse } = useCourse(courseId);
  const { data: progress, isLoading: progressLoading, error: progressError, refetch: refetchProgress } = useCourseProgress(courseId);
  const { data: weekPlans, isLoading: weeksLoading, error: weeksError } = useWeekPlans(courseId);

  const isLoading = courseLoading || progressLoading || weeksLoading;
  const hasError = courseError || progressError || weeksError;

  const [expandedWeek, setExpandedWeek] = useState<number>(1);

  // Update expanded week when course loads or progress changes
  useEffect(() => {
    if (progress?.current_week) {
      setExpandedWeek(progress.current_week);
    } else if (course?.current_week) {
      setExpandedWeek(course.current_week);
    }
  }, [course?.current_week, progress?.current_week]);

  if (isLoading) return <LoadingSkeleton />;
  if (hasError) {
    return (
      <ErrorBox 
        message={courseError || progressError || 'Unknown error'} 
        onRetry={() => {
          refetchCourse();
          refetchProgress();
        }} 
      />
    );
  }

  if (!course) {
    return (
      <div className={styles.page}>
        <div className={styles.errorBox}>
          <span className={styles.errorText}>✗ COURSE NOT FOUND</span>
          <Link href="/dashboard">
            <motion.button className={styles.retryBtn} whileHover={{ x: -2, y: -2 }}>
              BACK TO DASHBOARD →
            </motion.button>
          </Link>
        </div>
      </div>
    );
  }

  // Build weeks data from progress and weekPlans
  const weeks = weekPlans?.map((w: any) => {
    const p = progress?.week_progress?.find((wp: any) => wp.week === w.week_number);
    return {
      week: w.week_number,
      title: w.theme || `Week ${w.week_number}`,
      completed: p?.completed_days === p?.total_days,
      days: w.days?.map((d: any) => ({
        day: d.day_number,
        title: d.title || `Day ${d.day_number}`,
        completed: d.is_completed,
        current: course?.current_week === w.week_number && course?.current_day === d.day_number,
        locked: d.is_locked,
      })) || [],
      testCompleted: p?.test_completed || false,
      testScore: p?.test_score,
    };
  }) || [];

  // Get current day info from progress if available, otherwise fallback to course current_week/day
  const currentWeek = progress?.current_week ?? course.current_week ?? 1;
  const currentDay = progress?.current_day ?? course.current_day ?? 1;

  const currentWeekData = weeks.find((w: { week: number }) => w.week === currentWeek);
  const currentDayData = currentWeekData?.days.find((d: any) => d.day === currentDay);

  return (
    <div className={styles.page}>
      {/* Breadcrumb */}
      <div className={styles.breadcrumb}>
        <Link href="/dashboard">DASHBOARD</Link>
        <span className={styles.separator}>/</span>
        <span className={styles.current}>{(course.course_name || 'COURSE').toUpperCase()}</span>
      </div>

      <div className={styles.layout}>
        {/* Left: Week Navigation */}
        <div className={styles.weekNav}>
          <h3 className={styles.navTitle}>COURSE NAVIGATION</h3>
          
          <div className={styles.weeksList}>
            {weeks.map((weekData) => (
              <div key={weekData.week} className={styles.weekItem}>
                <button
                  className={`${styles.weekHeader} ${expandedWeek === weekData.week ? styles.expanded : ''}`}
                  onClick={() => setExpandedWeek(expandedWeek === weekData.week ? 0 : weekData.week)}
                >
                  <span className={styles.expandIcon}>
                    {expandedWeek === weekData.week ? '▼' : '►'}
                  </span>
                  <span className={styles.weekTitle}>
                    WEEK {weekData.week} — {weekData.title}
                  </span>
                  {weekData.completed && <span className={styles.checkMark}>✓</span>}
                </button>
                
                {expandedWeek === weekData.week && (
                  <motion.div
                    className={styles.daysList}
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    transition={{ duration: 0.2 }}
                  >
                    {weekData.days.map((day: any) => (
                      <Link
                        key={day.day}
                        href={`/dashboard/courses/${courseId}/week/${weekData.week}/day/${day.day}`}
                        className={`${styles.dayItem} ${day.completed ? styles.completed : ''} ${currentWeek === weekData.week && currentDay === day.day ? styles.current : ''} ${day.locked ? styles.locked : ''}`}
                      >
                        <span className={styles.dayBox}>
                          {day.completed ? '■' : day.locked ? '🔒' : '□'}
                        </span>
                        <span className={styles.dayText}>
                          Day {day.day}: {day.title}
                        </span>
                        {day.completed && <span className={styles.dayCheck}>✓</span>}
                      </Link>
                    ))}
                    
                    <Link
                      href={`/dashboard/courses/${courseId}/week/${weekData.week}/test`}
                      className={`${styles.testLink} ${weekData.testCompleted ? styles.completed : ''} ${!weekData.completed && weekData.days.every((d: any) => d.completed) ? '' : styles.locked}`}
                    >
                      <span className={styles.testIcon}>[TEST]</span>
                      <span>Week {weekData.week} Test</span>
                      {weekData.testCompleted && (
                        <span className={styles.testScore}>{weekData.testScore}%</span>
                      )}
                    </Link>
                  </motion.div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right: Course Overview */}
        <div className={styles.mainContent}>
          <motion.div
            className={styles.courseHeader}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
          >
            <h1 className={styles.courseName}>{course.course_name}</h1>
            <div className={styles.courseMeta}>
              <span className={styles.topic}>{course.topic}</span>
              <span className={styles.divider}>·</span>
              <span>{course.duration_weeks} WEEKS</span>
            </div>
          </motion.div>

          {/* Progress Bar */}
          <div className={styles.progressSection}>
            <div className={styles.progressHeader}>
              <span className={styles.progressLabel}>OVERALL PROGRESS</span>
              <span className={styles.progressValue}>{course.progress || progress?.progress || 0}%</span>
            </div>
            <div className={styles.progressBar}>
              <motion.div
                className={styles.progressFill}
                initial={{ width: 0 }}
                animate={{ width: `${course.progress || progress?.progress || 0}%` }}
                transition={{ duration: 0.8 }}
              />
            </div>
          </div>

          {/* Current Day Preview */}
          <motion.div
            className={styles.currentDayCard}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <div className={styles.cardLabel}>
              <span className={styles.labelIcon}>►</span>
              CURRENT DAY
            </div>
            
            <h2 className={styles.currentDayTitle}>
              WEEK {currentWeek} · DAY {currentDay}{currentDayData ? `: ${currentDayData.title}` : ''}
            </h2>
            
            <div className={styles.statsRow}>
              <div className={styles.stat}>
                <span className={styles.statLabel}>DAY</span>
                <span className={styles.statValue}>{currentDay} OF 5</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>WEEK</span>
                <span className={styles.statValue}>{currentWeek} OF {course.duration_weeks}</span>
              </div>
              <div className={styles.stat}>
                <span className={styles.statLabel}>COMPLETE</span>
                <span className={styles.statValue}>{course.progress || progress?.progress || 0}%</span>
              </div>
            </div>
            
            <Link href={`/dashboard/courses/${courseId}/week/${currentWeek}/day/${currentDay}`}>
              <motion.button
                className={styles.goBtn}
                whileHover={{ x: -2, y: -2 }}
                whileTap={{ scale: 0.98 }}
              >
                GO TO TODAY'S LESSON →
              </motion.button>
            </Link>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
