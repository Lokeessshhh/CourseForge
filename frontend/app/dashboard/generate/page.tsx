'use client';

import { useState, useEffect, Suspense } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams, useRouter } from 'next/navigation';
import { useGenerateCourse, useCourseStatus } from '@/app/hooks/api/useCourses';
import { Skeleton } from '@/app/components/Skeleton';
import styles from './page.module.css';

const durations = [
  { value: '1wk', label: '1WK', weeks: 1 },
  { value: '2wk', label: '2WK', weeks: 2 },
  { value: '1mo', label: '1MO', weeks: 4 },
  { value: '2mo', label: '2MO', weeks: 8 },
  { value: '3mo', label: '3MO', weeks: 12 },
];

const skillLevels = ['beginner', 'intermediate', 'advanced'] as const;

function LoadingSkeleton() {
  return (
    <div className={styles.page}>
      <div className={styles.formView}>
        <Skeleton width="100%" height="400px" />
      </div>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className={styles.errorBox}>
      <span className={styles.errorText}>✗ GENERATION FAILED · {message}</span>
    </div>
  );
}

function GenerateContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  
  const { generate, isGenerating, error: generateError } = useGenerateCourse();
  
  const [courseId, setCourseId] = useState<string | null>(null);
  const [topic, setTopic] = useState(searchParams.get('topic') || '');
  const [duration, setDuration] = useState(searchParams.get('duration') || '2wk');
  const [skillLevel, setSkillLevel] = useState<(typeof skillLevels)[number]>(
    (searchParams.get('skillLevel') as typeof skillLevels[number]) || 'intermediate'
  );
  const [goals, setGoals] = useState<string[]>([]);
  const [goalInput, setGoalInput] = useState('');
  const [hoursPerDay, setHoursPerDay] = useState(2);

  // Poll for status updates when courseId is set
  const { status, isLoading: statusLoading, error: statusError } = useCourseStatus(
    courseId || '',
    courseId ? 3000 : 0 // Poll every 3 seconds
  );

  const isComplete = status?.status === 'completed';
  const isFailed = status?.status === 'failed' || generateError || statusError;

  const handleAddGoal = () => {
    if (goalInput.trim() && goals.length < 5) {
      setGoals([...goals, goalInput.trim()]);
      setGoalInput('');
    }
  };

  const handleRemoveGoal = (index: number) => {
    setGoals(goals.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    if (!topic.trim()) return;

    const durationWeeks = durations.find(d => d.value === duration)?.weeks || 2;
    
    const result = await generate({
      course_name: topic,
      duration_weeks: durationWeeks,
      level: skillLevel,
      goals: goals.length > 0 ? goals : undefined,
      hours_per_day: hoursPerDay,
    });

    if (result?.id) {
      setCourseId(result.id);
    }
  };

  const handleStartLearning = () => {
    if (courseId) {
      router.push(`/dashboard/courses/${courseId}`);
    }
  };

  // Generation view
  if (courseId && status) {
    return (
      <div className={styles.page}>
        <motion.div
          className={styles.generationView}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
        >
          <div className={styles.sectionLabel}>
            <span className={styles.labelIcon}>►</span>
            GENERATING YOUR COURSE
          </div>
          
          <h1 className={styles.courseTopic}>{status.topic}</h1>
          
          <div className={styles.progressInfo}>
            WEEK {Math.ceil((status.completed_days || 0) / 5)} OF {status.weeks?.length || 0} · {status.completed_days || 0}/{status.total_days || 0} DAYS READY
          </div>
          
          <div className={styles.skeletonGrid}>
            {status.weeks?.map((week, weekIndex) => (
              <div key={week.week} className={styles.weekColumn}>
                <div className={styles.weekHeader}>WEEK {week.week}</div>
                <div className={styles.daysGrid}>
                  {week.days?.map((day, dayIndex) => (
                    <motion.div
                      key={day.day}
                      className={`${styles.dayCell} ${styles[day.status]}`}
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      transition={{ delay: weekIndex * 0.1 + dayIndex * 0.05 }}
                    >
                      {day.status === 'completed' && (
                        <span className={styles.dayTitle}>{day.title}</span>
                      )}
                      {day.status === 'generating' && (
                        <span className={styles.pulseAnimation}>...</span>
                      )}
                      {day.status === 'pending' && (
                        <span className={styles.lockedIcon}>🔒</span>
                      )}
                    </motion.div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          
          <AnimatePresence>
            {isFailed && (
              <motion.div
                className={styles.errorBox}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <h2 className={styles.errorTitle}>✗ GENERATION FAILED</h2>
                <p className={styles.errorText}>{generateError || statusError || 'An error occurred'}</p>
                <motion.button
                  className={styles.retryBtn}
                  onClick={() => setCourseId(null)}
                  whileHover={{ x: -2, y: -2 }}
                >
                  TRY AGAIN →
                </motion.button>
              </motion.div>
            )}
            
            {isComplete && (
              <motion.div
                className={styles.successBox}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              >
                <h2 className={styles.successTitle}>✓ COURSE READY</h2>
                <p className={styles.successText}>Your course has been generated successfully!</p>
                <motion.button
                  className={styles.startBtn}
                  onClick={handleStartLearning}
                  whileHover={{ x: -2, y: -2 }}
                  whileTap={{ scale: 0.98 }}
                >
                  START LEARNING →
                </motion.button>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    );
  }

  // Loading state during initial generation
  if (isGenerating) {
    return (
      <div className={styles.page}>
        <motion.div
          className={styles.generationView}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <div className={styles.sectionLabel}>
            <span className={styles.labelIcon}>►</span>
            STARTING GENERATION
          </div>
          <div className={styles.skeletonBox} style={{ width: '100%', height: '300px' }} />
        </motion.div>
      </div>
    );
  }

  // Form view
  return (
    <div className={styles.page}>
      <motion.div
        className={styles.formView}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className={styles.sectionLabel}>
          <span className={styles.labelIcon}>►</span>
          BUILD YOUR COURSE
        </div>
        
        <div className={styles.formCard}>
          {/* Topic */}
          <div className={styles.field}>
            <label className={styles.label}>TOPIC</label>
            <input
              type="text"
              className={styles.input}
              placeholder="e.g. Python Programming"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
            />
          </div>
          
          {/* Duration */}
          <div className={styles.field}>
            <label className={styles.label}>DURATION</label>
            <div className={styles.options}>
              {durations.map((d) => (
                <button
                  key={d.value}
                  className={`${styles.optionBtn} ${duration === d.value ? styles.selected : ''}`}
                  onClick={() => setDuration(d.value)}
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>
          
          {/* Skill Level */}
          <div className={styles.field}>
            <label className={styles.label}>SKILL LEVEL</label>
            <div className={styles.options}>
              {skillLevels.map((level) => (
                <button
                  key={level}
                  className={`${styles.optionBtn} ${skillLevel === level ? styles.selected : ''}`}
                  onClick={() => setSkillLevel(level)}
                >
                  {level.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          
          {/* Goals */}
          <div className={styles.field}>
            <label className={styles.label}>GOALS (MAX 5)</label>
            <div className={styles.goalsInput}>
              <input
                type="text"
                className={styles.input}
                placeholder="Type a goal and press Enter"
                value={goalInput}
                onChange={(e) => setGoalInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleAddGoal();
                  }
                }}
              />
            </div>
            {goals.length > 0 && (
              <div className={styles.goalsList}>
                {goals.map((goal, index) => (
                  <span key={index} className={styles.goalTag}>
                    {goal}
                    <button onClick={() => handleRemoveGoal(index)}>×</button>
                  </span>
                ))}
              </div>
            )}
          </div>
          
          {/* Hours Per Day */}
          <div className={styles.field}>
            <label className={styles.label}>HOURS PER DAY</label>
            <div className={styles.options}>
              {[1, 2, 3, 4].map((h) => (
                <button
                  key={h}
                  className={`${styles.optionBtn} ${hoursPerDay === h ? styles.selected : ''}`}
                  onClick={() => setHoursPerDay(h)}
                >
                  {h}
                </button>
              ))}
            </div>
          </div>
          
          {/* Submit */}
          <motion.button
            className={styles.submitBtn}
            onClick={handleSubmit}
            whileHover={{ x: -2, y: -2 }}
            whileTap={{ scale: 0.98 }}
            disabled={!topic.trim()}
          >
            CREATE COURSE →
          </motion.button>
        </div>
      </motion.div>
    </div>
  );
}

export default function GeneratePage() {
  return (
    <Suspense fallback={<LoadingSkeleton />}>
      <GenerateContent />
    </Suspense>
  );
}
