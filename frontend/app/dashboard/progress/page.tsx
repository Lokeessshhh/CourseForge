'use client';

import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { useUserProgress } from '@/app/hooks/api';
import styles from './page.module.css';

function StatBox({ label, value, delay }: { label: string; value: number; delay: number }) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const duration = 1000;
    const steps = 30;
    const increment = value / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) {
        setDisplayValue(value);
        clearInterval(timer);
      } else {
        setDisplayValue(Math.floor(current));
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [value]);

  return (
    <motion.div
      className={styles.statBox}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
    >
      <span className={styles.statLabel}>{label}</span>
      <span className={styles.statValue}>{displayValue}</span>
    </motion.div>
  );
}

function LoadingSkeleton() {
  return (
    <div className={styles.page}>
      {[1, 2, 3, 4, 5].map(i => (
        <div key={i} className={styles.skeletonBox} style={{ width: '100%', height: '200px', marginBottom: '32px' }} />
      ))}
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

// Generate streak calendar data from activity
const generateStreakCalendar = (activity: { date: string; minutes: number }[] = []) => {
  const calendar: { studied: boolean; minutes: number }[][] = [];
  const today = new Date();
  const activityMap = new Map(activity.map(a => [a.date, a.minutes]));
  
  for (let week = 0; week < 52; week++) {
    const weekDays: { studied: boolean; minutes: number }[] = [];
    for (let day = 0; day < 7; day++) {
      const date = new Date(today);
      date.setDate(date.getDate() - (51 - week) * 7 - (6 - day));
      const dateStr = date.toISOString().split('T')[0];
      const minutes = activityMap.get(dateStr) || 0;
      weekDays.push({ 
        studied: minutes > 0 && date <= today, 
        minutes 
      });
    }
    calendar.push(weekDays);
  }
  return calendar;
};

export default function ProgressPage() {
  const { data: progress, isLoading, error, refetch } = useUserProgress();
  
  const [conceptFilter, setConceptFilter] = useState<'all' | 'weak' | 'strong'>('all');
  const [sortByWeakest, setSortByWeakest] = useState(true);

  const streakCalendar = useMemo(() => {
    return progress?.streak_calendar?.weeks || [];
  }, [progress?.streak_calendar]);

  const filteredConcepts = useMemo(() => {
    let filtered = [...(progress?.concepts || [])];
    
    if (conceptFilter === 'weak') {
      filtered = filtered.filter(c => c.mastery < 50);
    } else if (conceptFilter === 'strong') {
      filtered = filtered.filter(c => c.mastery >= 80);
    }
    
    if (sortByWeakest) {
      filtered.sort((a, b) => a.mastery - b.mastery);
    }
    
    return filtered;
  }, [progress?.concepts, conceptFilter, sortByWeakest]);

  if (isLoading) return <LoadingSkeleton />;
  if (error) {
    return <ErrorBox message={error} onRetry={refetch} />;
  }

  const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC'];
  const currentMonth = new Date().getMonth();

  return (
    <div className={styles.page}>
      {/* Section 1: Overview Stats */}
      <section className={styles.section}>
        <div className={styles.sectionLabel}>
          <span className={styles.labelIcon}>►</span>
          OVERVIEW STATS
        </div>
        <div className={styles.statsGrid}>
          <StatBox label="DAYS COMPLETED" value={progress?.overall?.total_days_completed || 0} delay={0.1} />
          <StatBox label="COURSES ACTIVE" value={progress?.overall?.courses_active || 0} delay={0.15} />
          <StatBox label="LONGEST STREAK" value={progress?.overall?.longest_streak || 0} delay={0.2} />
          <StatBox label="AVG QUIZ SCORE" value={progress?.overall?.avg_quiz_score || 0} delay={0.25} />
        </div>
      </section>

      {/* Section 2: Streak Calendar */}
      <section className={styles.section}>
        <div className={styles.sectionLabel}>
          <span className={styles.labelIcon}>►</span>
          STUDY STREAK
        </div>
        <div className={styles.calendarCard}>
          <div className={styles.monthLabels}>
            {months.map((month, i) => (
              <span 
                key={month} 
                className={`${styles.monthLabel} ${i === currentMonth ? styles.currentMonth : ''}`}
              >
                {month}
              </span>
            ))}
          </div>
          <div className={styles.calendarGrid}>
            {streakCalendar.map((week, weekIndex) => (
              <div key={weekIndex} className={styles.weekColumn}>
                {week.map((studied, dayIndex) => (
                  <motion.div
                    key={dayIndex}
                    className={`${styles.calendarDay} ${studied ? styles.studied : ''} ${weekIndex === 51 && dayIndex === new Date().getDay() ? styles.today : ''}`}
                    title={studied ? 'Studied' : 'No activity'}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: weekIndex * 0.01 + dayIndex * 0.002 }}
                  />
                ))}
              </div>
            ))}
          </div>
          <div className={styles.dayLabels}>
            <span>S</span>
            <span>M</span>
            <span>T</span>
            <span>W</span>
            <span>T</span>
            <span>F</span>
            <span>S</span>
          </div>
        </div>
      </section>

      {/* Section 3: Course Progress */}
      <section className={styles.section}>
        <div className={styles.sectionLabel}>
          <span className={styles.labelIcon}>►</span>
          COURSE PROGRESS
        </div>
        <div className={styles.coursesList}>
          {progress?.courses?.map((course, index) => (
            <motion.div
              key={course.course_id}
              className={styles.courseCard}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <div className={styles.courseHeader}>
                <h3 className={styles.courseName}>{course.course_name}</h3>
                <span className={styles.courseTopic}>{course.topic}</span>
              </div>
              <div className={styles.courseProgressBar}>
                <motion.div
                  className={styles.courseProgressFill}
                  initial={{ width: 0 }}
                  animate={{ width: `${course.progress}%` }}
                  transition={{ duration: 0.8, delay: index * 0.1 }}
                />
              </div>
              <span className={styles.courseProgressText}>{course.progress}% COMPLETE</span>
              
              <div className={styles.weekBreakdown}>
                {course.weeks.map((w) => (
                  <div key={w.week} className={styles.weekItem}>
                    <span className={styles.weekNum}>W{w.week}</span>
                    <div className={styles.weekMiniBar}>
                      <div 
                        className={styles.weekMiniFill}
                        style={{ width: `${(w.completed_days / w.total_days) * 100}%` }}
                      />
                    </div>
                    {w.test_score !== null && (
                      <span className={styles.weekTestScore}>{w.test_score}%</span>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Section 4: Concept Mastery */}
      <section className={styles.section}>
        <div className={styles.sectionLabel}>
          <span className={styles.labelIcon}>►</span>
          CONCEPT MASTERY
        </div>
        <div className={styles.conceptControls}>
          <div className={styles.filterBtns}>
            {['all', 'weak', 'strong'].map((filter) => (
              <button
                key={filter}
                className={`${styles.filterBtn} ${conceptFilter === filter ? styles.active : ''}`}
                onClick={() => setConceptFilter(filter as typeof conceptFilter)}
              >
                {filter.toUpperCase()}
              </button>
            ))}
          </div>
          <label className={styles.sortToggle}>
            <input
              type="checkbox"
              checked={sortByWeakest}
              onChange={(e) => setSortByWeakest(e.target.checked)}
            />
            <span>SORT BY WEAKEST</span>
          </label>
        </div>
        <div className={styles.conceptList}>
          {filteredConcepts.map((concept, index) => (
            <motion.div
              key={concept.concept}
              className={styles.conceptRow}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <span className={styles.conceptName}>{concept.concept}</span>
              <div className={styles.conceptBar}>
                <motion.div
                  className={`${styles.conceptFill} ${concept.mastery < 40 ? styles.weak : ''}`}
                  initial={{ width: 0 }}
                  animate={{ width: `${concept.mastery}%` }}
                  transition={{ duration: 0.6, delay: index * 0.05 }}
                />
              </div>
              <span className={styles.conceptPercent}>{concept.mastery}%</span>
              <span className={styles.conceptPracticed}>PRACTICED {concept.practiced_count}x</span>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Section 5: Quiz History */}
      <section className={styles.section}>
        <div className={styles.sectionLabel}>
          <span className={styles.labelIcon}>►</span>
          QUIZ HISTORY
        </div>
        <div className={styles.quizTable}>
          <div className={styles.tableHeader}>
            <span>DATE</span>
            <span>COURSE</span>
            <span>DAY</span>
            <span>SCORE</span>
            <span>RESULT</span>
          </div>
          {progress?.quiz_history?.map((quiz, index) => (
            <motion.div
              key={index}
              className={styles.tableRow}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: index * 0.03 }}
            >
              <span>{quiz.date}</span>
              <span>{quiz.course}</span>
              <span>{quiz.day}</span>
              <span>{quiz.score}%</span>
              <span className={quiz.passed ? styles.passed : styles.failed}>
                {quiz.passed ? '✓ PASS' : '✗ FAIL'}
              </span>
            </motion.div>
          ))}
        </div>
      </section>
    </div>
  );
}
