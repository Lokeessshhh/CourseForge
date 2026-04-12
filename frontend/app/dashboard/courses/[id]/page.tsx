'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useApiClient } from '@/app/hooks/useApiClient';
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
        <span className={styles.errorText}> FAILED TO LOAD · {message}</span>
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
  const router = useRouter();
  const courseId = params.id as string;
  const api = useApiClient();

  const { data: course, isLoading: courseLoading, error: courseError, refetch: refetchCourse } = useCourse(courseId);
  const { data: progress, isLoading: progressLoading, error: progressError, refetch: refetchProgress } = useCourseProgress(courseId);
  const { data: weekPlans, isLoading: weeksLoading, error: weeksError } = useWeekPlans(courseId);

  const [deleting, setDeleting] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Track unlocked days for real-time updates
  const [unlockedDays, setUnlockedDays] = useState<Set<string>>(new Set());

  // SSE listener for real-time day unlocking
  useEffect(() => {
    if (!courseId) return;

    let eventSource: EventSource | null = null;
    let reconnectTimeout: NodeJS.Timeout | null = null;
    let isCancelled = false;

    const connectSSE = () => {
      if (isCancelled) return;

      // We MUST use the full backend URL (port 8000) because Next.js dev server 
      // does not correctly proxy SSE streams (it buffers them or returns 404).
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      const sseUrl = `${backendUrl}/api/courses/${courseId}/progress/sse/`;
      
      console.log(` Connecting to SSE: ${sseUrl}`);
      console.log(`ℹ If this shows localhost:3000, please Hard Refresh (Ctrl+Shift+R)`);
      
      eventSource = new EventSource(sseUrl);

      eventSource.onopen = () => {
        console.log(' SSE connected for real-time updates');
      };

      eventSource.onerror = (error) => {
        // SSE onerror fires with an empty Event object during normal reconnects.
        // This is expected behavior and not an actual error.
        console.warn(' SSE connection paused (reconnecting...)');
        // Auto-reconnect after 3 seconds
        if (!isCancelled) {
          reconnectTimeout = setTimeout(connectSSE, 3000);
        }
      };

      // Listen for day_complete events
      eventSource.addEventListener('day_complete', (event: MessageEvent) => {
        try {
          const parsed = JSON.parse(event.data);
          const { week_number, day_number, is_locked, theory_generated, code_generated, quiz_generated } = parsed.data || {};

          if (week_number && day_number) {
            const dayKey = `${week_number}-${day_number}`;
            console.log(` Day ${dayKey} completed and unlocked!`, {
              is_locked,
              theory_generated,
              code_generated,
              quiz_generated,
            });

            // Update unlocked days set
            setUnlockedDays(prev => {
              const next = new Set(prev);
              next.add(dayKey);
              return next;
            });

            // Refresh week plans to get latest data
            refetchProgress();
          }
        } catch (err) {
          console.error('Failed to parse SSE day_complete event:', err);
        }
      });

      // Listen for complete event (generation finished)
      eventSource.addEventListener('complete', (event: MessageEvent) => {
        console.log(' Course generation complete - closing SSE');
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
        // Refresh all data
        refetchCourse();
        refetchProgress();
      });
    };

    connectSSE();

    // Cleanup on unmount
    return () => {
      isCancelled = true;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (eventSource) {
        eventSource.close();
        eventSource = null;
      }
    };
  }, [courseId]);

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

  const handleDeleteCourse = async () => {
    setDeleting(true);
    try {
      await api.delete(`/api/courses/${courseId}/delete/`);
      router.push('/dashboard/courses');
    } catch (err) {
      alert('Failed to delete course');
      console.error('Delete course error:', err);
      setDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

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
          <span className={styles.errorText}> COURSE NOT FOUND</span>
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
    
    // Check coding test completion from week plan
    const codingTest1Completed = w.coding_test_1_completed || false;
    const codingTest2Completed = w.coding_test_2_completed || false;
    const allCodingTestsCompleted = codingTest1Completed && codingTest2Completed;
    
    // Week is fully complete when all days AND coding tests are done
    const weekFullyComplete = p?.completed_days === p?.total_days && allCodingTestsCompleted;

    return {
      week: w.week_number,
      title: w.theme || `Week ${w.week_number}`,
      completed: p?.completed_days === p?.total_days,
      fullyComplete: weekFullyComplete,
      codingTest1Completed,
      codingTest2Completed,
      testUnlocked: w.test_unlocked || false,
      days: w.days?.map((d: any) => ({
        day: d.day_number,
        title: d.title || `Day ${d.day_number}`,
        completed: d.is_completed,
        current: course?.current_week === w.week_number && course?.current_day === d.day_number,
        locked: d.is_locked,
      })) || [],
      testCompleted: p?.test_completed || false,
      testScore: p?.test_score,
      codingTest1Unlocked: w.coding_test_1_unlocked || false,
      codingTest2Unlocked: w.coding_test_2_unlocked || false,
      weeklyTestFullyComplete: p?.test_completed && (codingTest1Completed || codingTest2Completed),
    };
  }) || [];

  // Get current day info from progress if available, otherwise fallback to course current_week/day
  // CRITICAL: Default to Week 1, Day 1 for new courses - users should ALWAYS start from the beginning
  const currentWeek = Math.max(1, progress?.current_week ?? course.current_week ?? 1);
  const currentDay = Math.max(1, progress?.current_day ?? course.current_day ?? 1);

  const currentWeekData = weeks.find((w: { week: number }) => w.week === currentWeek);
  const currentDayData = currentWeekData?.days.find((d: any) => d.day === currentDay);

  // Check if weekly test should be displayed:
  // - All 5 days of current week are completed
  // - Weekly test is unlocked but not yet passed
  const allDaysInWeekCompleted = currentWeekData?.days.every((d: any) => d.completed);
  const weeklyTestUnlocked = currentWeekData?.testUnlocked;
  const weeklyTestPassed = currentWeekData?.testCompleted;
  const showWeeklyTest = allDaysInWeekCompleted && weeklyTestUnlocked && !weeklyTestPassed;

  return (
    <div className={styles.page}>
      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
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
                This will permanently delete "{course.course_name}" and all progress, quizzes, tests, and certificates.
              </p>
              <p className={styles.modalWarning}>This action cannot be undone.</p>
            </div>
            <div className={styles.modalActions}>
              <button
                className={styles.modalCancelBtn}
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleting}
              >
                CANCEL
              </button>
              <button
                className={`${styles.modalDeleteBtn} ${deleting ? styles.deleting : ''}`}
                onClick={handleDeleteCourse}
                disabled={deleting}
              >
                {deleting ? 'DELETING...' : 'DELETE'}
              </button>
            </div>
          </motion.div>
        </div>
      )}

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
                  {/* Show weekly test indicator when unlocked but not completed */}
                  {!weekData.fullyComplete && weekData.testUnlocked && !weekData.testCompleted && (
                    <span className={styles.weeklyTestBadge}>TEST</span>
                  )}
                  {/* Only show week checkmark when ALL days AND tests are fully completed */}
                  {weekData.fullyComplete && <span className={styles.checkMark}></span>}
                </button>
                
                {expandedWeek === weekData.week && (
                  <motion.div
                    className={styles.daysList}
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    transition={{ duration: 0.2 }}
                  >
                    {weekData.days.map((day: any) => {
                      const dayKey = `${weekData.week}-${day.day}`;
                      const isRealtimeUnlocked = unlockedDays.has(dayKey);
                      const isLocked = day.locked && !isRealtimeUnlocked;
                      // Only show completed checkmark when day is ACTUALLY completed (quiz passed), not just unlocked
                      const isCompleted = day.completed;

                      return (
                        <Link
                          key={day.day}
                          href={isLocked ? '#' : `/dashboard/courses/${courseId}/week/${weekData.week}/day/${day.day}`}
                          className={`${styles.dayItem} ${isCompleted ? styles.completed : ''} ${currentWeek === weekData.week && currentDay === day.day ? styles.current : ''} ${isLocked ? styles.locked : ''}`}
                          onClick={(e) => {
                            if (isLocked) {
                              e.preventDefault();
                            }
                          }}
                        >
                          <span className={styles.dayBox}>
                            {isCompleted ? '■' : isLocked ? 'LOCK' : day.title ? '□' : '...'}
                          </span>
                          <span className={styles.dayText}>
                            Day {day.day}: {day.title || 'Generating...'}
                          </span>
                          {/* Only show checkmark when day is truly completed, not just unlocked/generating */}
                          {isCompleted && <span className={styles.dayCheck}></span>}
                          {isRealtimeUnlocked && !day.completed && (
                            <span className={styles.generatingBadge}> Just unlocked!</span>
                          )}
                        </Link>
                      );
                    })}

                    {/* Single unified weekly test container */}
                    {(() => {
                      const mcqDone = weekData.testCompleted;
                      const codingDone = weekData.codingTest1Completed;
                      const bothDone = mcqDone && codingDone;
                      const testLocked = !weekData.testUnlocked;

                      // Case 1: Both MCQ and Coding done → Show completed (non-clickable) with checkmark
                      if (bothDone) {
                        return (
                          <div className={`${styles.testLink} ${styles.completed} ${styles.locked}`}>
                            <span className={styles.testIcon}>[TEST]</span>
                            <span> Week Test Completed</span>
                            <span className={styles.dayCheck}></span>
                          </div>
                        );
                      }

                      // Case 2: MCQ done, coding not done → Link to coding test
                      if (mcqDone && !codingDone) {
                        return (
                          <Link
                            href={`/dashboard/courses/${courseId}/week/${weekData.week}/coding-test/1`}
                            className={`${styles.testLink} ${styles.completed}`}
                          >
                            <span className={styles.testIcon}>[TEST]</span>
                            <span>Week {weekData.week} Coding Test</span>
                            <span className={styles.testScore}>MCQ Done → Code</span>
                          </Link>
                        );
                      }

                      // Case 3: Neither done → Link to MCQ test (if unlocked)
                      return (
                        <Link
                          href={!testLocked ? `/dashboard/courses/${courseId}/week/${weekData.week}/test` : '#'}
                          className={`${styles.testLink} ${testLocked ? styles.locked : ''}`}
                          onClick={(e) => {
                            if (testLocked) e.preventDefault();
                          }}
                        >
                          <span className={styles.testIcon}>[TEST]</span>
                          <span>Week {weekData.week} Test</span>
                          {weekData.testScore !== null && weekData.testScore !== undefined && (
                            <span className={styles.testScore}>{weekData.testScore}%</span>
                          )}
                        </Link>
                      );
                    })()}
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
            <div className={styles.courseHeaderTop}>
              <h1 className={styles.courseName}>{course.course_name}</h1>
              <motion.button
                className={`${styles.deleteCourseBtn} ${deleting ? styles.deleting : ''}`}
                onClick={() => setShowDeleteConfirm(true)}
                disabled={deleting}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                title="Delete course"
              >
                {deleting ? 'DELETING...' : 'DELETE COURSE'}
              </motion.button>
            </div>
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
            className={`${styles.currentDayCard} ${showWeeklyTest ? styles.weeklyTestCard : ''}`}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <div className={styles.cardLabel}>
              <span className={styles.labelIcon}>►</span>
              {showWeeklyTest ? 'WEEKLY TEST READY' : 'CURRENT DAY'}
            </div>

            {showWeeklyTest ? (
              <>
                <h2 className={styles.currentDayTitle}>
                  WEEK {currentWeek} · WEEKLY TEST
                </h2>

                <div className={styles.statsRow}>
                  <div className={styles.stat}>
                    <span className={styles.statLabel}>STATUS</span>
                    <span className={styles.statValue}>READY TO ATTEMPT</span>
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

                <Link href={`/dashboard/courses/${courseId}/week/${currentWeek}/test`}>
                  <motion.button
                    className={`${styles.goBtn} ${styles.testBtn}`}
                    whileHover={{ x: -2, y: -2 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    START WEEKLY TEST →
                  </motion.button>
                </Link>
              </>
            ) : (
              <>
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
              </>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
}
